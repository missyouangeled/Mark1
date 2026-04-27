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
  { title: '夜航派对', text: '限时讨论活动 · 参与话题可点亮夜光徽章', badge: 'NOW', icon: '🌌' },
  { title: '编辑推荐墙', text: '6 位编辑轮流上墙，展示“今晚真想玩”的理由', badge: 'HOT', icon: '🧠' },
  { title: '开黑招募', text: '自动聚合同类型玩家偏好，像论坛招募贴一样直给', badge: 'NEW', icon: '🎮' }
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
    <div className="pb-28 pt-10 md:pb-48 md:pt-20">
      <section className="page-shell">
        {/* Main Hero Bento Grid */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:grid-rows-2">
          
          {/* Feature Hero - Large Spanning Block */}
          <div className="glass hero-panel relative overflow-hidden rounded-[40px] border border-white/10 col-span-1 lg:col-span-8 lg:row-span-2 p-8 md:p-12 flex flex-col justify-between">
            <div className="relative z-10 space-y-8">
              <div className="brand-chip inline-flex rounded-full px-4 py-1.5 text-xs font-bold tracking-wider text-emerald-100 uppercase">
                Featured this week · {featured.tag}
              </div>
              <h1 className="max-w-4xl text-5xl font-bold leading-tight tracking-tighter text-white md:text-7xl lg:text-8xl">
                先被氛围钩住，<br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-300 to-sky-400">再被热度留下来。</span>
              </h1>
              <p className="max-w-xl text-lg leading-relaxed text-white/60 md:text-xl">
                像逛热门论坛首页一样，在PulseNest体验真正的社区感。加入热榜、活动卡、实时动态，让游戏探索不再孤单。
              </p>
              <div className="flex flex-wrap gap-4">
                <Link href={`/game/${featured.slug}`} className="inline-flex items-center justify-center rounded-full bg-emerald-400 px-8 py-4 text-sm font-bold text-slate-950 transition-transform hover:scale-105 active:scale-95">
                  进入主推详情
                </Link>
                <Link href="/discover" className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/5 px-8 py-4 text-sm font-medium text-white transition-hover hover:bg-white/10">
                  探索发现页
                </Link>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-8 mt-16 relative z-10">
              {heroStats.map(([label, num, note]) => (
                <div key={label} className="rounded-2xl border border-white/5 bg-white/5 p-8 backdrop-blur-sm">
                  <div className="text-[10px] uppercase tracking-widest text-white/40 font-bold">{label}</div>
                  <div className="mt-2 text-3xl font-bold text-white">{num}</div>
                  <div className="mt-1 text-xs text-soft">{note}</div>
                </div>
              ))}
            </div>

            {/* Hero Visual - Floating Element */}
            <div className="absolute -right-20 -bottom-20 w-2/3 h-2/3 bg-gradient-to-br from-emerald-500/20 to-sky-500/20 rounded-full blur-[120px] pointer-events-none" />
          </div>

          {/* Hot Board - Medium Block */}
          <div className="glass bento-item rounded-[40px] p-8 col-span-1 lg:col-span-4 lg:row-span-1 flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <div className="text-sm font-bold uppercase tracking-widest text-emerald-300">Hot Board</div>
              <span className="text-[10px] px-2 py-1 rounded-full bg-rose-500/20 text-rose-200 border border-rose-500/30">LIVE</span>
            </div>
            <div className="flex-1 space-y-3 overflow-hidden">
              {hotThreads.map(([rank, title, heat]) => (
                <div key={title} className="group flex items-center gap-4 p-3 rounded-2xl transition-colors hover:bg-white/5">
                  <div className="text-lg font-black text-white/20 group-hover:text-emerald-400 transition-colors">{rank}</div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-white/90 truncate group-hover:text-white">{title}</div>
                    <div className="text-[10px] text-soft">{heat}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Pulse Feed - Medium Block */}
          <div className="glass bento-item rounded-[40px] p-8 col-span-1 lg:col-span-4 lg:row-span-1 flex flex-col">
            <div className="text-sm font-bold uppercase tracking-widest text-emerald-300 mb-6">Pulse Feed</div>
            <div className="flex-1 space-y-4">
              {pulseFeed.map(([time, text]) => (
                <div key={text} className="flex gap-3 items-start">
                  <div className="mt-1.5 h-2 w-2 rounded-full bg-emerald-400 pulse-dot" />
                  <div>
                    <div className="text-[10px] text-white/40 font-medium">{time}</div>
                    <div className="text-xs leading-relaxed text-white/80">{text}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Middle Section: Focus Slots & Tag Cloud */}
      <section className="page-shell mt-32 grid grid-cols-1 gap-8 lg:grid-cols-12">
        
        {/* Focus Slots - Bento style */}
        <div className="lg:col-span-8 grid grid-cols-1 sm:grid-cols-3 gap-8">
          {liveCards.map((item, index) => (
            <div key={item.title} className={`focus-card bento-item relative overflow-hidden rounded-[32px] p-8 text-white flex flex-col justify-between min-h-[240px] ${index === 0 ? 'focus-1' : index === 1 ? 'focus-2' : 'focus-3'}`}>
              <div className="absolute right-6 top-6 rounded-full bg-black/30 backdrop-blur-md px-3 py-1 text-[10px] font-bold text-white border border-white/10">
                {item.badge}
              </div>
              <div className="text-5xl mb-6">{item.icon}</div>
              <div>
                <div className="text-2xl font-bold mb-2">{item.title}</div>
                <div className="text-sm text-white/80 leading-relaxed">{item.text}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Tag Cloud - Right Panel */}
        <div className="glass bento-item rounded-[32px] p-8 lg:col-span-4 flex flex-col justify-between">
          <div>
            <div className="text-sm font-bold uppercase tracking-widest text-emerald-300 mb-6">Tag Cloud</div>
            <div className="flex flex-wrap gap-2">
              {tagCloud.map((tag) => (
                <button key={tag} className="tag-cloud-item px-4 py-2 rounded-full border border-white/10 bg-white/5 text-xs font-medium text-white hover:border-emerald-400/50 transition-colors">
                  {tag}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-8 p-5 rounded-2xl border border-white/5 bg-white/[0.02] backdrop-blur-sm">
            <div className="text-xs font-bold text-white/40 uppercase tracking-tighter mb-3">Community Mood</div>
            <div className="flex items-center gap-4">
              <div className="h-1.5 flex-1 rounded-full bg-white/10 overflow-hidden">
                <div className="h-full w-[74%] bg-gradient-to-r from-emerald-400 to-sky-400" />
              </div>
              <span className="text-sm font-bold text-white">74%</span>
            </div>
            <p className="mt-3 text-xs text-soft leading-relaxed">
              本日更偏向“高颜值 + 轻沉浸 + 轻分享”的内容情绪。
            </p>
          </div>
        </div>
      </section>

      {/* Trending Section: Asymmetrical Grid */}
      <section className="page-shell mt-32">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
          <div className="max-w-2xl">
            <div className="text-sm font-bold uppercase tracking-widest text-emerald-300 mb-2">Trending Now</div>
            <h2 className="text-4xl font-bold tracking-tighter text-white md:text-5xl">最近讨论度最高的候选</h2>
          </div>
          <div className="ticker-strip rounded-full border border-white/10 bg-white/5 px-6 py-3 text-xs text-white/60 font-medium">
            🔥 热议中：剧情浓度 / 四人开黑 / 年度美术 / 夜游氛围 / 独立黑马 / 机甲拼装
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-12">
          {trending.map((game) => (
            <GameCard key={game.slug} game={game} />
          ))}
        </div>
      </section>

      {/* Bottom Section: Authors & High Rated */}
      <section className="page-shell mt-32 grid grid-cols-1 lg:grid-cols-12 gap-12">
        
        {/* Editors' Notes - Large block */}
        <div className="glass bento-item rounded-[40px] p-10 lg:col-span-7 flex flex-col justify-between">
          <div>
            <div className="text-sm font-bold uppercase tracking-widest text-emerald-300 mb-4">Editors' Notes</div>
            <h3 className="text-3xl font-bold text-white mb-6 tracking-tight">为什么这种内容结构更像真实会停留的社区站</h3>
            <p className="text-lg text-white/60 leading-relaxed mb-12 max-w-2xl">
              热门论坛/社区不是只靠大图，而是把‘值得点开’‘正在发生’‘我还能去哪’同时摆在首页，让人自然停留。
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
              {[
                ['强视觉焦点位', 'Hero、活动卡、热帖角标形成“第一眼就有内容密度”'],
                ['右侧高频信息', '热榜、动态、标签云、推荐作者都是留人装置'],
                ['轻互动暗示', '悬浮 dock、状态按钮、动态脉冲、hover 微动效']
              ].map(([title, text]) => (
                <div key={title} className="p-8 rounded-2xl border border-white/5 bg-white/[0.03] text-center">
                  <div className="text-base font-bold text-white mb-2">{title}</div>
                  <div className="text-xs text-soft leading-relaxed">{text}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Authors & Rankings - Right Column Bento */}
        <div className="lg:col-span-5 grid grid-cols-1 gap-8">
          
          {/* Recommended Authors */}
          <div className="glass bento-item rounded-[32px] p-8 flex flex-col">
            <div className="text-sm font-bold uppercase tracking-widest text-emerald-300 mb-6">Recommended Authors</div>
            <div className="space-y-4">
              {authors.map((author) => (
                <div key={author.name} className="group flex items-center gap-4 p-4 rounded-2xl border border-white/5 bg-white/[0.03] transition-colors hover:bg-white/10">
                  <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/10 ${author.glow} text-xl`}>🏅</div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white truncate">{author.name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-400/20 text-amber-200 border border-amber-400/30">认证</span>
                    </div>
                    <div className="text-xs text-soft truncate">{author.tag}</div>
                  </div>
                  <div className="text-sm font-bold text-emerald-400">{author.score}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Top Rated Speed-view */}
          <div className="glass bento-item rounded-[32px] p-8 flex flex-col">
            <div className="text-sm font-bold uppercase tracking-widest text-emerald-300 mb-6">Top Rated</div>
            <div className="space-y-3">
              {ranked.slice(0, 4).map((game, index) => (
                <Link key={game.slug} href={`/game/${game.slug}`} className="group flex items-center gap-4 p-3 rounded-2xl border border-white/5 bg-white/[0.03] transition-all hover:bg-white/10 hover:pl-6">
                  <div className="text-lg font-black text-white/20 group-hover:text-emerald-400 transition-colors">#{index + 1}</div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-bold text-white truncate group-hover:text-emerald-100 transition-colors">{game.title}</div>
                    <div className="text-sm text-soft truncate">{game.subtitle}</div>
                  </div>
                  <div className="text-sm font-bold text-emerald-400">{game.rating.toFixed(1)}</div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
