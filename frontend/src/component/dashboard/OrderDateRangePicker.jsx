"use client";

import { useMemo } from "react";
import { FiCalendar, FiX } from "react-icons/fi";
import { parseDate } from "@internationalized/date";
import { Group } from "react-aria-components";
import {
  DateRangePickerPopover,
  DateRangePickerRoot,
  DateRangePickerTrigger,
  DateRangePickerTriggerIndicator,
  RangeCalendarCell,
  RangeCalendarGrid,
  RangeCalendarGridBody,
  RangeCalendarGridHeader,
  RangeCalendarHeader,
  RangeCalendarHeaderCell,
  RangeCalendarHeading,
  RangeCalendarNavButton,
  RangeCalendarRoot,
} from "@heroui/react";

// "YYYY-MM-DD" -> "Sep 23, 2026", built from the plain calendar-date string only (never a JS Date/timezone), so
// it can never disagree with what was actually selected or what the backend will actually filter by.
export function formatCalendarDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" });
}

// The "Order Date" filter (single day or an inclusive range) on Order Management, built on @heroui/react's
// DateRangePicker/RangeCalendar (React Aria underneath — the project's first date picker, so range selection,
// keyboard nav, Escape-to-close and outside-click aren't reinvented here). `value`/`onChange` deal only in plain
// "YYYY-MM-DD" strings — exactly what apps.orders.filters.OrderFilter's date_from/date_to already expect — and
// CalendarDate is timezone-naive by construction, so there's no UTC-shift risk converting to/from it; picking the
// SAME day for both ends of the range is how this calendar expresses "one day" (RangeCalendar's own interaction
// model, not custom logic here).
export default function OrderDateRangePicker({ value, onChange }) {
  const calendarValue = useMemo(() => (value ? { start: parseDate(value.start), end: parseDate(value.end) } : null), [value]);

  function handleChange(range) {
    onChange(range ? { start: range.start.toString(), end: range.end.toString() } : null);
  }

  const label = !value
    ? "Select date range"
    : value.start === value.end
      ? formatCalendarDate(value.start)
      : `${formatCalendarDate(value.start)} - ${formatCalendarDate(value.end)}`;

  return (
    <div className="flex items-center gap-2">
      <DateRangePickerRoot aria-label="Order date filter" value={calendarValue} onChange={handleChange}>
        {/* react-aria-components' DateRangePicker anchors its Popover to this Group's own DOM node (see
            react-aria-components/dist/private/DatePicker: groupRef is passed as both the Group's ref AND the
            Popover's triggerRef) — without a real <Group> here the popover has no anchor to measure and renders
            unpositioned instead of under the trigger. */}
        <Group>
          <DateRangePickerTrigger className="checkout-input flex items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm">
            <FiCalendar className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className={value ? "" : "showcase-muted"}>{label}</span>
            <DateRangePickerTriggerIndicator className="showcase-muted ml-1" />
          </DateRangePickerTrigger>
        </Group>
        <DateRangePickerPopover className="order-date-picker__popover">
          <RangeCalendarRoot>
            <RangeCalendarHeader className="order-date-picker__header">
              <RangeCalendarNavButton slot="previous" className="order-date-picker__nav">
                &lsaquo;
              </RangeCalendarNavButton>
              <RangeCalendarHeading className="order-date-picker__heading" />
              <RangeCalendarNavButton slot="next" className="order-date-picker__nav">
                &rsaquo;
              </RangeCalendarNavButton>
            </RangeCalendarHeader>
            <RangeCalendarGrid>
              <RangeCalendarGridHeader>{(day) => <RangeCalendarHeaderCell>{day}</RangeCalendarHeaderCell>}</RangeCalendarGridHeader>
              <RangeCalendarGridBody>{(date) => <RangeCalendarCell date={date} />}</RangeCalendarGridBody>
            </RangeCalendarGrid>
          </RangeCalendarRoot>
        </DateRangePickerPopover>
      </DateRangePickerRoot>

      {value && (
        <button type="button" onClick={() => onChange(null)} aria-label="Clear date filter" className="showcase-muted hover:text-current" title="Clear">
          <FiX className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
