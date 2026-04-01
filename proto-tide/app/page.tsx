import Link from 'next/link';
import { GameCard } from '@/components/game-card';
import { SectionTitle } from '@/components/section-title';
import { featured, ranked, trending } from '@/data/games';

const heroStats = [
  ['72h 热帖', '268', '比昨日 +18%'],
  ['活跃作者', '1.3k', '创作氛围稳定上扬'],
  ['正在围观', '24.6k', '首页实时滚动中']
];

const hotThreads = [
  ['#1', '为什么《Starfall Zero》一眼就有“年度相”', '12.8k 热度'],
  ['#2', '四人开黑到底该冲哪款？这三款越聊越上头', '9.4k 热度'],
  ['#3', '本周最适合熬夜沉浸的剧情向作品整理', '7.1k 热度'],
  ['#4', '轻策略不是轻深度：Mech Haven 的系统感太顺了', '6.3k 热度']
];

const liveCards = [
  { title: '夜航派对', text: '限时讨论活动 · 参与话题可点亮夜光徽章', badge: 'NOW' },
  { title: '编辑推荐墙', text: '6 位编辑轮流上墙，展示“今晚真想玩”的理由', badge: 'HOT' },
  { title: '开黑招募', text: '自动聚合同类型玩家偏好，像论坛招募贴一样直给', badge: 'NEW' }
];

const authors = [
  { name: 'Rin', tag: '氛围叙事观察者', score: '92%', note: '擅长把“好不好玩”拆成能读懂的情绪结构。', glow: 'bg-fuchsia-400/20' },
  { name: 'Kite', tag: '联机机制控', score: '88%', note: '喜欢从角色协作、节奏和局内反馈聊设计。', glow: 'bg-sky-400/20' },
  { name: 'Moss', tag: '独立游戏挖掘机', score: '95%', note: '总能从小体量作品里翻出惊喜与审美亮点。', glow: 'bg-emerald-400/20' }
];

const tagCloud = ['#今晚玩什么', '#高分独立', '#开黑四排', '#剧情浓度', '#机甲经营', '#像素新宠', '#买断推荐', '#氛围党集合'];

const pulseFeed = [
  ['19 秒前', '有 36 位玩家正在围观 “夜航派对” 活动卡'],
  ['2 分钟前', '本周热帖榜单更新，Starfall Zero 再次登顶'],
  ['5 分钟前', '编辑精选新增 2 个“适合下班后放空”的清单']
];

export default function HomePage() {
  return (
    <div className="pb-28 pt-10 md:pb-36 md:pt-14">
      <section className="page-shell">
        <div className="items-stretch grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="glass hero-panel flex h-full overflow-hidden rounded-[36px] border border-white/10">
            <div className="grid gap-8 p-6 md:grid-cols-[1.15fr_0.85fr] md:p-8 lg:p-10">
              <div className="flex flex-col justify-between gap-8">
                <div className="space-y-5">
                  <div className="brand-chip inline-flex rounded-full px-4 py-2 text-sm font-medium text-emerald-100">
                    本周焦点 · {featured.tag} · 热榜第一候选
                  </div>
                  <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-white md:text-6xl">
                    像逛热门论坛首页一样，先被氛围钩住，再被热度和观点留下来。
                  </h1>
                  <p className="max-w-2xl text-base leading-8 text-white/70 md:text-lg">
                    这轮增强把 PulseNest 从“漂亮原型”往“更像真实热门社区站”推进：加入热榜、活动卡、标签云、作者推荐、实时动态、悬浮操作和更明显的论坛感信息编排。
                  </p>
                </div>
                <div className="flex flex-col gap-4 sm:flex-row">
                  <Link href={`/game/${featured.slug}`} className="inline-flex items-center justify-center rounded-full bg-[linear-gradient(135deg,#23d3a2,#6df0cf)] px-6 py-3 text-sm font-semibold text-slate-950">
                    进入主推详情
                  </Link>
                  <Link href="/discover" className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/5 px-6 py-3 text-sm font-medium text-white/88">
                    去看发现页专题
                  </Link>
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  {heroStats.map(([label, num, note]) => (
                    <div key={label} className="rounded-3xl border border-white/8 bg-white/4 p-4">
                      <div className="text-xs uppercase tracking-[0.28em] text-white/42">{label}</div>
                      <div className="mt-2 text-2xl font-semibold text-white">{num}</div>
                      <div className="mt-1 text-sm text-soft">{note}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                <div className={`${featured.accentClass} relative h-[320px] overflow-hidden rounded-[30px] border border-white/10 md:h-full`}>
                  <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/10 to-transparent" />
                  <div className="absolute inset-x-0 top-0 flex items-center justify-between p-5 md:p-6">
                    <span className="rounded-full border border-white/14 bg-black/18 px-3 py-1 text-xs text-white/86">Forum Pick</span>
                    <span className="rounded-full bg-rose-400/18 px-3 py-1 text-xs text-rose-100">热帖角标</span>
                  </div>
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

          <aside className="grid h-full gap-6 xl:auto-rows-fr">
            <div className="glass h-full rounded-[32px] p-6 md:p-7">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">Hot Board</div>
                  <div className="mt-2 text-2xl font-semibold">右侧热榜</div>
                </div>
                <span className="rounded-full border border-rose-300/18 bg-rose-300/10 px-3 py-1 text-xs text-rose-100">论坛感增强</span>
              </div>
              <div className="mt-6 space-y-3">
                {hotThreads.map(([rank, title, heat]) => (
                  <div key={title} className="rounded-3xl border border-white/8 bg-white/[0.03] p-4 transition hover:border-white/14 hover:bg-white/[0.05]">
                    <div className="flex items-start gap-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/6 text-sm font-semibold text-white/90">{rank}</div>
                      <div className="min-w-0 flex-1">
                        <div className="line-clamp-2 text-sm font-medium leading-6 text-white/90">{title}</div>
                        <div className="mt-1 text-xs text-soft">{heat}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass h-full rounded-[32px] p-6 md:p-7">
              <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">Pulse Feed</div>
              <div className="mt-4 space-y-3">
                {pulseFeed.map(([time, text]) => (
                  <div key={text} className="flex gap-3 rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">
                    <div className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-300 pulse-dot" />
                    <div>
                      <div className="text-xs text-white/42">{time}</div>
                      <div className="mt-1 text-sm leading-6 text-white/84">{text}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="page-shell mt-32 items-stretch grid gap-6 md:mt-36 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="glass h-full rounded-[32px] p-7 md:p-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">Focus Slots</div>
              <div className="mt-2 text-2xl font-semibold">焦点位 / 活动卡 / 论坛运营位</div>
            </div>
            <span className="text-sm text-soft">全用渐变、SVG/emoji、抽象块面表达，无侵权素材</span>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {liveCards.map((item, index) => (
              <div key={item.title} className={`focus-card focus-${index + 1} relative overflow-hidden rounded-[28px] border border-white/10 p-5`}>
                <div className="absolute right-4 top-4 rounded-full bg-black/18 px-3 py-1 text-xs text-white/86">{item.badge}</div>
                <div className="text-3xl">{index === 0 ? '🌌' : index === 1 ? '🧠' : '🎮'}</div>
                <div className="mt-8 text-xl font-semibold text-white">{item.title}</div>
                <div className="mt-3 text-sm leading-7 text-white/78">{item.text}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass h-full rounded-[32px] p-7 md:p-8">
          <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">Tag Cloud</div>
          <div className="mt-3 text-2xl font-semibold">标签云 / 轻入口导航</div>
          <div className="mt-6 flex flex-wrap gap-3">
            {tagCloud.map((tag, index) => (
              <button
                key={tag}
                className={`tag-cloud-item rounded-full border px-4 py-2 text-sm transition hover:-translate-y-0.5 ${index % 3 === 0 ? 'border-emerald-300/22 bg-emerald-300/10 text-emerald-100' : index % 3 === 1 ? 'border-sky-300/18 bg-sky-300/10 text-sky-100' : 'border-fuchsia-300/18 bg-fuchsia-300/10 text-fuchsia-100'}`}
              >
                {tag}
              </button>
            ))}
          </div>
          <div className="mt-8 rounded-[26px] border border-white/8 bg-white/[0.03] p-5">
            <div className="text-sm text-white/46">今日社区情绪</div>
            <div className="mt-4 flex items-center gap-3">
              <div className="h-3 flex-1 overflow-hidden rounded-full bg-white/8">
                <div className="h-full w-[74%] rounded-full bg-[linear-gradient(90deg,#23d3a2,#77e7ff,#b06df0)]" />
              </div>
              <div className="text-sm font-semibold text-white">74%</div>
            </div>
            <p className="mt-3 text-sm leading-7 text-soft">本日更偏向“高颜值 + 轻沉浸 + 适合分享观点”的内容，说明社区不只是找游戏，也在找表达欲。</p>
          </div>
        </div>
      </section>

      <section className="page-shell mt-32 space-y-16 md:mt-40 md:space-y-20">
        <SectionTitle
          kicker="Trending Now"
          title="最近讨论度最高的 3 款候选"
          description="继续保留原本稳定的卡片浏览逻辑，同时给卡片所在区域加入更像热门站首页的“正在热聊”语境。"
        />
        <div className="ticker-strip rounded-full border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-white/70">
          🔥 热议中：剧情浓度 / 四人开黑 / 年度美术 / 夜游氛围 / 独立黑马 / 机甲拼装 / 轻竞速叙事
        </div>
        <div className="grid gap-14 md:gap-16 lg:grid-cols-3 lg:gap-24 xl:gap-28 2xl:gap-32">
          {trending.map((game) => (
            <GameCard key={game.slug} game={game} />
          ))}
        </div>
      </section>

      <section className="page-shell mt-28 items-stretch grid gap-12 md:mt-32 lg:grid-cols-[1.2fr_0.8fr] lg:gap-14">
        <div className="glass h-full rounded-[34px] p-8 md:p-10">
          <SectionTitle
            kicker="Editors' Notes"
            title="为什么这种内容结构更像真实会停留的社区站"
            description="热门论坛/社区不是只靠大图，而是把‘值得点开’‘正在发生’‘我还能去哪’同时摆在首页，让人自然停留。"
          />
          <div className="mt-16 grid gap-6 md:mt-20 md:grid-cols-3 md:gap-7">
            {[
              ['强视觉焦点位', 'Hero、活动卡、热帖角标形成“第一眼就有内容密度”的效果。'],
              ['右侧高频信息', '热榜、动态、标签云、推荐作者都是论坛首页常见留人装置。'],
              ['轻互动暗示', '悬浮 dock、状态按钮、动态脉冲、hover 微动效，能让页面更像活着的社区。']
            ].map(([title, text]) => (
              <div key={title} className="rounded-3xl border border-white/8 bg-white/[0.03] p-6">
                <div className="text-lg font-semibold">{title}</div>
                <p className="mt-3 text-sm leading-7 text-soft">{text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid h-full gap-6 auto-rows-fr">
          <div className="glass h-full rounded-[32px] p-7 md:p-9">
            <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">Recommended Authors</div>
            <div className="mt-3 text-2xl font-semibold">推荐作者 / 勋章感名片</div>
            <div className="mt-6 space-y-4">
              {authors.map((author) => (
                <div key={author.name} className="rounded-[26px] border border-white/8 bg-white/[0.03] p-4">
                  <div className="flex items-center gap-4">
                    <div className={`flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 ${author.glow}`}>🏅</div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 text-white">
                        <span className="font-semibold">{author.name}</span>
                        <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-0.5 text-[11px] text-amber-100">认证作者</span>
                      </div>
                      <div className="mt-1 text-sm text-soft">{author.tag}</div>
                    </div>
                    <div className="text-sm font-semibold text-emerald-300">{author.score}</div>
                  </div>
                  <p className="mt-3 text-sm leading-7 text-white/72">{author.note}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="glass h-full rounded-[32px] p-7 md:p-9">
            <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">Top Rated</div>
            <div className="mt-4 text-2xl font-semibold">高分速览</div>
            <div className="mt-8 space-y-4 md:space-y-5">
              {ranked.slice(0, 4).map((game, index) => (
                <Link key={game.slug} href={`/game/${game.slug}`} className="flex items-center gap-5 rounded-3xl border border-white/8 bg-white/[0.03] px-5 py-5 transition hover:bg-white/[0.05] md:px-6 md:py-6">
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
        </div>
      </section>
    </div>
  );
}
