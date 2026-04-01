import Link from 'next/link';
import { SectionTitle } from '@/components/section-title';
import { ranked } from '@/data/games';

export default function RankingsPage() {
  return (
    <div className="page-shell pb-24 pt-10 md:pb-32 md:pt-14">
      <section className="glass rounded-[36px] p-7 md:p-9">
        <SectionTitle
          kicker="Rankings"
          title="排行榜：把社区判断浓缩成最容易扫读的列表"
          description="设计重点不是复杂筛选，而是让评分、热度、厂牌、平台信息在单个列表项里一屏说清楚，同时保留卡片式视觉质感。"
        />
      </section>

      <section className="mt-16 space-y-6 md:mt-20 md:space-y-7">
        {ranked.map((game, index) => (
          <Link
            key={game.slug}
            href={`/game/${game.slug}`}
            className="glass flex flex-col gap-6 rounded-[30px] p-6 transition hover:-translate-y-0.5 hover:border-emerald-300/28 md:flex-row md:items-center md:gap-7 md:p-7"
          >
            <div className="flex items-center gap-4 md:w-48">
              <div className="flex h-16 w-16 items-center justify-center rounded-[24px] bg-white/6 text-2xl font-semibold text-white/86">#{index + 1}</div>
              <div>
                <div className="text-xl font-semibold">{game.title}</div>
                <div className="mt-1 text-sm text-soft">{game.category}</div>
              </div>
            </div>

            <div className="min-w-0 flex-1">
              <div className="text-base text-white/84 md:text-lg">{game.subtitle}</div>
              <div className="mt-2 text-sm leading-7 text-soft">{game.summary}</div>
            </div>

            <div className="grid gap-3 text-sm md:w-[360px] md:grid-cols-3">
              <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                <div className="text-white/46">评分</div>
                <div className="mt-2 text-2xl font-semibold text-emerald-300">{game.rating.toFixed(1)}</div>
              </div>
              <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                <div className="text-white/46">厂牌</div>
                <div className="mt-2 font-medium text-white/90">{game.studio}</div>
              </div>
              <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                <div className="text-white/46">状态</div>
                <div className="mt-2 font-medium text-white/90">{game.update}</div>
              </div>
            </div>
          </Link>
        ))}
      </section>
    </div>
  );
}
