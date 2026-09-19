import time

import pytest
from django.db import connection, models

from apps.core.models import SoftDeleteModel, TimeStampedModel


class Thing(TimeStampedModel, SoftDeleteModel):
    name = models.CharField(max_length=20)

    class Meta:
        app_label = "core"


class Owner(models.Model):
    thing = models.ForeignKey(Thing, on_delete=models.CASCADE)

    class Meta:
        app_label = "core"


@pytest.fixture
def tables(db):
    # Postgres DDL is transactional: these tables vanish when the test's transaction rolls back.
    with connection.schema_editor() as editor:
        editor.create_model(Thing)
        editor.create_model(Owner)


def test_models_are_abstract():
    assert TimeStampedModel._meta.abstract and SoftDeleteModel._meta.abstract


def test_timestamps_are_set_and_updated(tables):
    thing = Thing.objects.create(name="a")
    assert thing.created_at and thing.updated_at
    created, first_updated = thing.created_at, thing.updated_at
    time.sleep(0.01)
    thing.name = "b"
    thing.save()
    thing.refresh_from_db()
    assert thing.created_at == created
    assert thing.updated_at > first_updated


def test_instance_delete_is_soft(tables):
    thing = Thing.objects.create(name="a")
    updated_before = thing.updated_at
    thing.delete()
    assert Thing.objects.count() == 0
    stored = Thing.all_objects.get(pk=thing.pk)
    assert stored.is_deleted and stored.deleted_at is not None
    assert stored.updated_at > updated_before


def test_queryset_delete_is_soft_and_returns_count(tables):
    Thing.objects.create(name="a")
    Thing.objects.create(name="b")
    assert Thing.objects.all().delete() == 2
    assert Thing.objects.count() == 0
    assert Thing.all_objects.count() == 2
    assert Thing.all_objects.dead().count() == 2


def test_restore(tables):
    thing = Thing.objects.create(name="a")
    thing.delete()
    Thing.all_objects.get(pk=thing.pk).restore()
    assert Thing.objects.filter(pk=thing.pk).exists()
    assert Thing.all_objects.get(pk=thing.pk).deleted_at is None
    Thing.all_objects.all().delete()
    Thing.all_objects.dead().restore()
    assert Thing.objects.count() == 1


def test_hard_delete_really_deletes(tables):
    thing = Thing.objects.create(name="a")
    thing.hard_delete()
    assert Thing.all_objects.count() == 0
    Thing.objects.create(name="b")
    Thing.objects.all().hard_delete()
    assert Thing.all_objects.count() == 0


def test_alive_and_default_manager_agree(tables):
    live = Thing.objects.create(name="live")
    Thing.objects.create(name="gone").delete()
    assert list(Thing.objects.alive()) == [live]
    assert list(Thing.all_objects.alive()) == [live]


def test_foreign_key_still_resolves_soft_deleted_target(tables):
    thing = Thing.objects.create(name="a")
    owner = Owner.objects.create(thing=thing)
    thing.delete()
    assert Owner.objects.get(pk=owner.pk).thing.name == "a"
