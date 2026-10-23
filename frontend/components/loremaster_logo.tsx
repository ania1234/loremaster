export function LoremasterLogo() {
  return (
    <div className="flex items-center gap-3 text-[#385A55]">
      <svg
        viewBox="0 0 48 48"
        className="size-12 shrink-0"
        fill="none"
        aria-hidden="true"
      >
        <rect x="1" y="1" width="46" height="46" rx="12" fill="currentColor" />
        <rect x="4" y="4" width="40" height="40" rx="9" stroke="#E1DCC6" strokeOpacity=".3" />
        <path
          d="M10 19c5-1 10 1 14 4 4-3 9-5 14-4v17c-5-1-10 0-14 3-4-3-9-4-14-3V19Z"
          fill="#F6F2E7"
          fillOpacity=".1"
          stroke="#F6F2E7"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path d="M24 23v16m-10-14 6 2m-6 3 6 2m8-5 6-2m-6 7 6-2" stroke="#F6F2E7" strokeWidth="1.25" strokeLinecap="round" />
        <path d="m24 8 1.9 4.6L30.5 14l-4.6 1.9L24 20.5l-1.9-4.6L17.5 14l4.6-1.4L24 8Z" fill="#D8BC7E" />
      </svg>
      <span className="font-serif text-2xl tracking-[-0.04em]">
        Lore<span className="italic">master</span>
      </span>
    </div>
  );
}
