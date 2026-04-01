import Link from 'next/link';
import { notFound } from 'next/navigation';
import { GameCard } from '@/components/game-card';
import { games } from '@/data/games';

export function generateStaticParams() {
  return games.map((game) => ({ slug: game.slug }));
}

export default async function GameDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const game = games.find((item) => item.slug === slug);

  if (!game) notFound();

  const recommendations = games.filter((item) => item.slug !== game.slug).slice(0, 3);

  return (
    <div className="page-shell pb-16 pt-8 md:pb-24 md:pt-10">
      <section className="glass overflow-hidden rounded-[36px] border border-white/10">
        <div className="grid gap-8 p-6 md:grid-cols-[0.9fr_1.1fr] md:p-8 lg:p-10">
          <div className={`${game.accentClass} relative min-h-[340px] overflow-hidden rounded-[32px] border border-white/10`}>
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/8 to-transparent" />
            <div className="absolute left-6 top-6">
              <span className="brand-chip rounded-full px-4 py-2 text-sm text-emerald-100">{game.tag}</span>
            </div>
            <div className="absolute inset-x-0 bottom-0 p-6 md:p-8">
              <div className="text-xs uppercase tracking-[0.35em] text-white/64">PulseNest Detail</div>
              <div className="mt-3 text-4xl font-semibold">{game.title}</div>
              <div className="mt-3 max-w-lg text-white/76">{game.hero}</div>
            </div>
          </div>

          <div className="flex flex-col gap-8">
            <div>
              <div className="text-sm uppercase tracking-[0.35em] text-emerald-300/88">{game.category}</div>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight md:text-5xl">{game.subtitle}</h1>
              <p className="mt-5 max-w-2xl text-base leading-8 text-white/74">{game.description}</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                <div className="text-sm text-white/46">综合评分</div>
                <div className="mt-2 text-3xl font-semibold text-emerald-300">{game.rating.toFixed(1)}</div>
              </div>
              <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                <div className="text-sm text-white/46">热度</div>
                <div className="mt-2 text-xl font-semibold text-white">{game.downloads}</div>
              </div>
              <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                <div className="text-sm text-white/46">获取方式</div>
                <div className="mt-2 text-xl font-semibold text-white">{game.price}</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              {game.platforms.map((platform) => (
                <span key={platform} className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/82">
                  {platform}
                </span>
              ))}
            </div>

            <div className="flex flex-col gap-4 sm:flex-row">
              <button className="rounded-full bg-[linear-gradient(135deg,#23d3a2,#6df0cf)] px-6 py-3 text-sm font-semibold text-slate-950">
                立即查看预约
              </button>
              <Link href="/rankings" className="rounded-full border border-white/10 bg-white/5 px-6 py-3 text-center text-sm font-medium text-white/86">
                返回排行榜
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-10 grid gap-8 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="glass rounded-[32px] p-6 md:p-8">
          <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">亮点摘要</div>
          <div className="mt-6 space-y-4">
            {game.bullets.map((item, index) => (
              <div key={item} className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                <div className="text-xs uppercase tracking-[0.3em] text-white/42">Point 0{index + 1}</div>
                <div className="mt-2 text-lg font-semibold text-white">{item}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass rounded-[32px] p-6 md:p-8">
          <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">版本与厂牌</div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {[
              ['工作室', game.studio],
              ['更新状态', game.update],
              ['一句话总结', game.summary],
              ['推荐原因', '视觉、结构和社区信息密度都很适合做高保真展示稿。']
            ].map(([label, value]) => (
              <div key={label} className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                <div className="text-sm text-white/46">{label}</div>
                <div className="mt-3 text-base leading-7 text-white/88">{value}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-10 space-y-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">You may also like</div>
            <div className="mt-3 text-2xl font-semibold">继续逛同站其他候选</div>
          </div>
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          {recommendations.map((item) => (
            <GameCard key={item.slug} game={item} compact />
          ))}
        </div>
      </section>
    </div>
  );
}
