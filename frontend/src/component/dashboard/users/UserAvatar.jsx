"use client";

import { useState } from "react";

// A user's avatar (User.avatar), or their initials when there's none or it fails to load.
export default function UserAvatar({ user, size = "h-9 w-9 text-xs" }) {
  const [failed, setFailed] = useState(false);
  const initials =
    (user.full_name || "")
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "?";

  if (user.avatar && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- remote avatar at a fixed small size
      <img src={user.avatar} alt="" onError={() => setFailed(true)} className={`${size} shrink-0 rounded-full object-cover`} />
    );
  }
  return (
    <span aria-hidden="true" className={`user-avatar ${size} flex shrink-0 items-center justify-center rounded-full font-semibold`}>
      {initials}
    </span>
  );
}
