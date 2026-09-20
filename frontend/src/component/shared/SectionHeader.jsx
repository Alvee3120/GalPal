// Editorial homepage section header: title | description | actions (arrows) in one row on desktop;
// on small screens the title and actions share a row with the description underneath.
// Shared by the product carousels and the shoppable video carousel.
export default function SectionHeader({ title, description, actions }) {
  return (
    <div className="mb-8 grid grid-cols-[minmax(0,1fr)_auto] items-end gap-x-6 gap-y-3 md:mb-10 lg:flex lg:justify-between lg:gap-x-12">
      <h2 className="custom-font max-w-[12em] text-3xl leading-[1.1] sm:text-4xl">{title}</h2>

      {/* Mobile: these two are placed straight into the grid (display: contents). Desktop: one right-hand group. */}
      <div className="contents lg:flex lg:min-w-0 lg:items-end lg:gap-10">
        {description && (
          <p className="showcase-muted col-span-2 row-start-2 max-w-md text-sm leading-relaxed lg:col-auto lg:row-auto lg:max-w-sm">
            {description}
          </p>
        )}
        {actions}
      </div>
    </div>
  );
}
