export function SectionTitle({ title, description, kicker }: { title: string; description: string; kicker: string }) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between md:gap-8">
      <div>
        <div className="text-sm font-medium uppercase tracking-[0.36em] text-emerald-300/88">{kicker}</div>
        <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white md:text-4xl">{title}</h2>
      </div>
      <p className="max-w-2xl text-sm leading-8 text-soft md:text-base">{description}</p>
    </div>
  );
}
