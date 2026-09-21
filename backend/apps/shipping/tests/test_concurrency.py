"""
Two admins editing at once. Real threads and real transactions (`transaction=True`), because the
rules under test are ones the database and row locks enforce, which a single-connection test that
rolls back can never exercise.
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from django.db import connection

from apps.shipping import services
from apps.shipping.models import DeliveryZone, ShippingChargeHistory

from .factories import DeliveryZoneFactory

ROUNDS = 6


def run_together(jobs):
    """Run each callable in its own thread and connection, released by a barrier; returns their results."""
    barrier = threading.Barrier(len(jobs))

    def wrap(job):
        try:
            barrier.wait(timeout=10)
            return job()
        except Exception as exc:  # noqa: BLE001 - the test inspects what came back
            return exc
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(wrap, jobs))


@pytest.mark.django_db(transaction=True)
def test_two_admins_making_different_zones_default_at_once_leave_exactly_one_default():
    for _ in range(ROUNDS):
        DeliveryZone.objects.all().delete()
        current = DeliveryZoneFactory(is_default=True)
        first, second = DeliveryZoneFactory(), DeliveryZoneFactory()

        def make_default(zone):
            def job():
                fresh = DeliveryZone.objects.get(pk=zone.pk)
                fresh.is_default = True
                return services.save_zone(fresh)
            return job

        results = run_together([make_default(first), make_default(second)])
        assert not [r for r in results if isinstance(r, Exception)], results
        defaults = DeliveryZone.objects.filter(is_default=True)
        assert defaults.count() == 1 and defaults.get().is_active
        assert defaults.get().pk in {first.pk, second.pk}
        assert not DeliveryZone.objects.get(pk=current.pk).is_default


@pytest.mark.django_db(transaction=True)
def test_concurrent_charge_changes_keep_an_unbroken_history_chain():
    zone = DeliveryZoneFactory(charge="100.00")
    new_charges = ["110.00", "120.00", "130.00", "140.00"]
    results = run_together([lambda c=c: services.change_charge(zone, c) for c in new_charges])
    assert not [r for r in results if isinstance(r, Exception)], results

    rows = list(ShippingChargeHistory.objects.filter(zone=zone).order_by("id"))
    assert len(rows) == len(new_charges)
    assert rows[0].old_charge == Decimal("100.00")
    for previous, following in zip(rows, rows[1:], strict=False):
        assert following.old_charge == previous.new_charge  # nothing lost, nothing recorded twice
    assert DeliveryZone.objects.get(pk=zone.pk).charge == rows[-1].new_charge


@pytest.mark.django_db(transaction=True)
def test_deleting_the_default_while_another_zone_is_being_made_default_never_leaves_none():
    from apps.catalog.exceptions import Conflict

    for _ in range(ROUNDS):
        DeliveryZone.objects.all().delete()
        current = DeliveryZoneFactory(is_default=True)
        challenger = DeliveryZoneFactory()

        def promote():
            fresh = DeliveryZone.objects.get(pk=challenger.pk)
            fresh.is_default = True
            return services.save_zone(fresh)

        results = run_together([promote, lambda: services.delete_zone(current)])
        unexpected = [r for r in results if isinstance(r, Exception) and not isinstance(r, Conflict)]
        assert not unexpected, results
        defaults = DeliveryZone.objects.filter(is_default=True)
        assert defaults.count() == 1 and defaults.get().is_active
