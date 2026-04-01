import Link from 'next/link';
import { GameCard } from '@/components/game-card';
import { SectionTitle } from '@/components/section-title';
import { games } from '@/data/games';

const tags = ['动作', '多人', '剧情', '买断', '高分', '独立', '模拟'];

export default function DiscoverPage() {
  return (
    <div className="page-shell pb-16 pt-8 md:pb-24 md:pt-10">
      <section className="glass rounded-[36px] p-6 md:p-8">
        <SectionTitle
          kicker="Discover"
          title="发现页：用标签、专题和推荐流继续逛"
          description="这里模拟的是偏社区导向的平台发现页——不是机械筛选，而是结合专题编排、热度推荐与类型标签，让内容像信息流一样自然下沉。"
        />
        <div className="mt-8 flex flex-wrap gap-3">
          {tags.map((tag) => (
            <button key={tag} className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/80 transition hover:border-emerald-300/30 hover:text-white">
              #{tag}
            </button>
          ))}
        </div>
      </section>

      <section className="mt-10 grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="glass rounded-[32px] p-6 md:p-8">
          <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">专题推荐</div>
          <h2 className="mt-3 text-3xl font-semibold">今晚值得熬夜的 4 种氛围</h2>
          <div className="mt-6 space-y-4">
            {[
              ['单机沉浸', '适合戴耳机慢慢推剧情，节奏稳。'],
              ['朋友开黑', '强调角色分工与即时配合，热闹但不乱。'],
              ['管理上头', '一旦开始排资源和升级就很难停下来。'],
              ['轻松上手', '打开就能玩，十分钟内进入状态。']
            ].map(([title, text], index) => (
              <div key={title} className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                <div className="text-xs uppercase tracking-[0.3em] text-white/42">0{index + 1}</div>
                <div className="mt-2 text-xl font-semibold">{title}</div>
                <p className="mt-2 text-sm leading-7 text-soft">{text}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {games.map((game) => (
            <GameCard key={game.slug} game={game} compact />
          ))}
        </div>
      </section>

      <section className="mt-10 glass rounded-[32px] p-6 md:p-8">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">继续浏览</div>
            <div className="mt-3 text-2xl font-semibold">如果你更相信排序，也可以直接看榜单</div>
          </div>
          <Link href="/rankings" className="inline-flex items-center justify-center rounded-full bg-[linear-gradient(135deg,#23d3a2,#6df0cf)] px-5 py-3 text-sm font-semibold text-slate-950">
            去排行榜
          </Link>
        </div>
      </section>
    </div>
  );
}
