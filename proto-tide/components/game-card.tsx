import Link from 'next/link';
import type { Game } from '@/data/games';
import { ArrowIcon, StarIcon } from './icons';

export function GameCard({ game, compact = false }: { game: Game; compact?: boolean }) {
  return (
    <Link
      href={`/game/${game.slug}`}
      className="glass group flex h-full flex-col overflow-hidden rounded-[30px] transition duration-300 hover:-translate-y-1 hover:border-emerald-300/28 hover:shadow-[0_24px_70px_rgba(35,211,162,0.18)]"
    >
      <div className={`${game.accentClass} relative ${compact ? 'h-52' : 'h-64'} w-full`}>
        <div className="absolute inset-x-0 top-0 flex items-center justify-between p-4">
          <span className="brand-chip rounded-full px-3 py-1 text-xs font-medium text-emerald-100">{game.tag}</span>
          <span className="rounded-full bg-black/24 px-3 py-1 text-xs text-white/90">{game.category}</span>
        </div>
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-4 pt-12">
          <div className="text-[1.35rem] font-semibold leading-tight">{game.title}</div>
          <div className="mt-1 text-sm text-white/76">{game.subtitle}</div>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-7 p-6 md:p-7">
        <p className="text-sm leading-7 text-white/74">{game.summary}</p>
        <div className="mt-auto flex items-center justify-between gap-3 pt-2 text-sm">
          <div className="flex items-center gap-2 text-amber-300">
            <StarIcon />
            <span className="font-semibold text-white">{game.rating.toFixed(1)}</span>
            <span className="text-soft">{game.downloads}</span>
          </div>
          <div className="flex items-center gap-1 text-emerald-300 transition group-hover:translate-x-1">
            查看详情
            <ArrowIcon />
          </div>
        </div>
      </div>
    </Link>
  );
}
