import Link from 'next/link';

const nav = [
  { href: '/', label: '首页' },
  { href: '/discover', label: '发现' },
  { href: '/rankings', label: '排行榜' }
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/8 bg-black/30 backdrop-blur-xl">
      <div className="header-glow border-b border-white/6">
        <div className="page-shell flex items-center justify-between gap-4 py-2 text-xs text-white/62">
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/16 bg-emerald-300/8 px-3 py-1 text-emerald-100">
              <span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_14px_rgba(109,240,207,0.85)]" />
              社区热度实时刷新中
            </span>
            <span>今日焦点：独立叙事 / 组队共斗 / 夜游氛围</span>
          </div>
          <div className="hidden lg:block">热门标签 #剧情 #开黑 #轻策略 #高分新作</div>
        </div>
      </div>

      <div className="page-shell flex items-center justify-between gap-5 py-5">
        <Link href="/" className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#23d3a2,#6df0cf)] text-lg font-black text-slate-950 shadow-[0_16px_40px_rgba(35,211,162,0.3)]">
            PN
          </div>
          <div>
            <div className="text-lg font-semibold tracking-wide">PulseNest</div>
            <div className="text-xs text-soft">像逛热门论坛一样找下一款会沉迷的游戏</div>
          </div>
        </Link>

        <nav className="hidden items-center gap-2 md:flex">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-full px-4 py-2 text-sm text-white/78 transition hover:bg-white/8 hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-3 sm:flex">
          <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/72">
            🔎 搜索榜单、话题、作者、游戏名
          </div>
          <button className="rounded-full bg-[linear-gradient(135deg,#23d3a2,#6df0cf)] px-4 py-2 text-sm font-semibold text-slate-950 transition hover:scale-[1.02]">
            登录体验
          </button>
        </div>
      </div>
    </header>
  );
}
