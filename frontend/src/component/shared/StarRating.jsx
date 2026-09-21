import { FaRegStar, FaStar, FaStarHalfAlt } from "react-icons/fa";

// Five-star rating drawn from the backend's average_rating (0-5) + review_count. Used only where a rating is
// meaningful at a glance (the Shop grid); other product cards opt out via ProductCard's `showRating` prop.
export default function StarRating({ rating, count, className = "" }) {
  const value = Math.max(0, Math.min(5, Number(rating) || 0));
  const full = Math.floor(value + 0.25); // >= .25 rounds the icon up to a half/full star
  const half = value - full >= -0.75 && value % 1 >= 0.25 && value % 1 < 0.75;

  return (
    <div className={`flex items-center gap-1 ${className}`} role="img" aria-label={`Rated ${value.toFixed(1)} out of 5${count ? ` from ${count} review${count === 1 ? "" : "s"}` : ""}`}>
      <span className="star-rating__stars flex" aria-hidden="true">
        {Array.from({ length: 5 }, (_, i) => {
          const Icon = i < full ? FaStar : i === full && half ? FaStarHalfAlt : FaRegStar;
          return <Icon key={i} className="h-3 w-3" />;
        })}
      </span>
      <span className="star-rating__score text-xs font-medium">{value.toFixed(1)}</span>
      {typeof count === "number" && count > 0 && <span className="showcase-muted text-xs">({count})</span>}
    </div>
  );
}
