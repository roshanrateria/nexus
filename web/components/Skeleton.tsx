"use client";

export function Skeleton() {
  return (
    <>
      <div className="glass lg:col-span-5 min-h-[320px] p-5">
        <SkeletonPanel rows={4} />
      </div>
      <div className="glass lg:col-span-4 min-h-[320px] p-5">
        <SkeletonPanel rows={2} />
      </div>
      <div className="glass lg:col-span-3 lg:row-span-2 min-h-[680px] p-5">
        <SkeletonPanel rows={9} />
      </div>
      <div className="glass lg:col-span-5 min-h-[300px] p-5">
        <SkeletonPanel rows={4} />
      </div>
      <div className="glass lg:col-span-4 min-h-[300px] p-5">
        <SkeletonPanel rows={3} />
      </div>
      <div className="glass lg:col-span-4 min-h-[300px] p-5">
        <SkeletonPanel rows={3} />
      </div>
      <div className="glass lg:col-span-8 min-h-[300px] p-5">
        <SkeletonPanel rows={5} />
      </div>
    </>
  );
}

function SkeletonPanel({ rows }: { rows: number }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="shimmer h-3 w-24" />
      {Array.from({ length: rows - 1 }, (_, i) => (
        <div key={i} className="shimmer" style={{ height: 14, width: widthFor(i), maxWidth: "100%" }} />
      ))}
    </div>
  );
}

function widthFor(i: number): string {
  const widths = ["86%", "62%", "74%", "48%", "92%", "56%", "70%", "38%", "80%"];
  return widths[i % widths.length];
}
