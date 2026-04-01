import Link from 'next/link';
import { GameCard } from '@/components/game-card';
import { SectionTitle } from '@/components/section-title';
import { featured, ranked, trending } from '@/data/games';

export default function HomePage() {
  return (
    <div className="pb-16 pt-8 md:pb-24 md:pt-10">
      <section className="page-shell">
        <div className="glass overflow-hidden rounded-[36px] border border-white/10">
          <div className="grid gap-8 p-6 md:grid-cols-[1.15fr_0.85fr] md:p-8 lg:p-10">
            <div className="flex flex-col justify-between gap-8">
              <div className="space-y-5">
                <div className="brand-chip inline-flex rounded-full px-4 py-2 text-sm font-medium text-emerald-100">
                  本周焦点 · {featured.tag}
                </div>
                <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-white md:text-6xl">
                  像逛游戏社区一样，找到真正想立刻下载的下一款作品。
                </h1>
                <p className="max-w-2xl text-base leading-8 text-white/70 md:text-lg">
                  PulseNest 是一个原创游戏内容原型站：视觉气质偏年轻、轻快、社区导向，整体体验参考热门移动游戏平台的内容结构，但品牌、文案和素材全部原创重做。
                </p>
              </div>
              <div className="flex flex-col gap-4 sm:flex-row">
                <Link href={`/game/${featured.slug}`} className="inline-flex items-center justify-center rounded-full bg-[linear-gradient(135deg,#23d3a2,#6df0cf)] px-6 py-3 text-sm font-semibold text-slate-950">
                  进入主推详情
                </Link>
                <Link href="/discover" className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/5 px-6 py-3 text-sm font-medium text-white/88">
                  逛发现页
                </Link>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                {[
                  ['9.4+', '均分风格化展示'],
                  ['3 个主页面', '首页 / 详情 / 排行'],
                  ['Responsive', '移动端与桌面端适配']
                ].map(([num, label]) => (
                  <div key={num} className="rounded-3xl border border-white/8 bg-white/4 p-4">
                    <div className="text-2xl font-semibold text-white">{num}</div>
                    <div className="mt-1 text-sm text-soft">{label}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className={`${featured.accentClass} relative h-[320px] overflow-hidden rounded-[30px] border border-white/10 md:h-full`}>
                <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/10 to-transparent" />
                <div className="absolute inset-x-0 bottom-0 p-6 md:p-8">
                  <div className="text-xs uppercase tracking-[0.35em] text-emerald-200/80">Hero Pick</div>
                  <div className="mt-3 text-3xl font-semibold">{featured.title}</div>
                  <div className="mt-2 text-white/72">{featured.hero}</div>
                  <div className="mt-6 flex flex-wrap gap-2">
                    {featured.platforms.map((platform) => (
                      <span key={platform} className="rounded-full border border-white/14 bg-black/18 px-3 py-1 text-xs text-white/84">
                        {platform}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="page-shell mt-16 space-y-8">
        <SectionTitle
          kicker="Trending Now"
          title="最近讨论度最高的 3 款候选"
          description="卡片区沿用了熟悉的社区浏览逻辑：封面、标签、评分、热度一眼可读，快速决定要不要点进详情。"
        />
        <div className="grid gap-6 lg:grid-cols-3">
          {trending.map((game) => (
            <GameCard key={game.slug} game={game} />
          ))}
        </div>
      </section>

      <section className="page-shell mt-16 grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="glass rounded-[32px] p-6 md:p-8">
          <SectionTitle
            kicker="Editors' Notes"
            title="为什么这种内容结构会让人停留更久"
            description="首页不是单纯卖图，而是同时提供‘当前最值得点开哪一个’与‘接下来还能继续逛什么’的路径。"
          />
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {[
              ['强视觉首屏', '用大 Hero 区承接情绪与品类气质，快速建立站点调性。'],
              ['轻社区信息', '评分、热度、标签在卡片层就完成判断，不必点进去才知道值不值得。'],
              ['多入口分流', '首页看主推，发现页看分类，排行榜看排序，让用户每一步都有自然去向。']
            ].map(([title, text]) => (
              <div key={title} className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                <div className="text-lg font-semibold">{title}</div>
                <p className="mt-3 text-sm leading-7 text-soft">{text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="glass rounded-[32px] p-6 md:p-8">
          <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">Top Rated</div>
          <div className="mt-3 text-2xl font-semibold">高分速览</div>
          <div className="mt-6 space-y-4">
            {ranked.slice(0, 4).map((game, index) => (
              <Link key={game.slug} href={`/game/${game.slug}`} className="flex items-center gap-4 rounded-3xl border border-white/8 bg-white/[0.03] p-4 transition hover:bg-white/[0.05]">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/6 text-lg font-semibold text-white/80">#{index + 1}</div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-white">{game.title}</div>
                  <div className="truncate text-sm text-soft">{game.subtitle}</div>
                </div>
                <div className="text-sm font-semibold text-emerald-300">{game.rating.toFixed(1)}</div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
