import Link from 'next/link';
import { GameCard } from '@/components/game-card';
import { SectionTitle } from '@/components/section-title';
import { games } from '@/data/games';

const tags = ['动作', '多人', '剧情', '买断', '高分', '独立', '模拟', '开黑', '夜游'];
const columns = [
  {
    title: '今晚值得熬夜的 4 种氛围',
    items: [
      ['单机沉浸', '适合戴耳机慢慢推剧情，节奏稳。'],
      ['朋友开黑', '强调角色分工与即时配合，热闹但不乱。'],
      ['管理上头', '一旦开始排资源和升级就很难停下来。'],
      ['轻松上手', '打开就能玩，十分钟内进入状态。']
    ]
  },
  {
    title: '社区正在收藏的专题',
    items: [
      ['像论坛精华帖那样的推荐单', '不是纯筛选，而是带观点、带语气、带场景的整理。'],
      ['通勤碎片时间可玩', '适合 15 分钟内开一局，退出也不心疼。'],
      ['拍照分享欲很强', '适合截图、晒 UI、晒美术、晒角色氛围。'],
      ['下班后放空清单', '低压力但不无聊，适合心情需要一点柔软的时候。']
    ]
  }
];

export default function DiscoverPage() {
  return (
    <div className="page-shell pb-28 pt-10 md:pb-36 md:pt-14">
      <section className="glass rounded-[36px] p-7 md:p-9">
        <SectionTitle
          kicker="Discover"
          title="发现页：更像真正会不停下滑的社区专题流"
          description="把标签、专题、推荐流、运营位摆在一起，形成一种更接近热门论坛/社区的浏览节奏：不靠复杂筛选，靠‘你会忍不住再看一眼’。"
        />
        <div className="mt-8 flex flex-wrap gap-3">
          {tags.map((tag, index) => (
            <button
              key={tag}
              className={`rounded-full border px-4 py-2 text-sm transition hover:border-emerald-300/30 hover:text-white ${index % 3 === 0 ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-100' : index % 3 === 1 ? 'border-sky-300/18 bg-sky-300/8 text-sky-100' : 'border-white/10 bg-white/5 text-white/80'}`}
            >
              #{tag}
            </button>
          ))}
        </div>
      </section>

      <section className="mt-10 grid gap-6 lg:grid-cols-[1fr_0.82fr]">
        <div className="glass rounded-[32px] p-6 md:p-7">
          <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">Scrolling Spotlight</div>
          <div className="mt-3 grid gap-4 md:grid-cols-3">
            {['🌠 夜游氛围', '🧩 机制上头', '🎧 音乐先赢一半'].map((item, index) => (
              <div key={item} className={`focus-card focus-${index + 1} rounded-[26px] border border-white/10 p-5`}>
                <div className="text-2xl">{item.split(' ')[0]}</div>
                <div className="mt-8 text-lg font-semibold text-white">{item.split(' ').slice(1).join(' ')}</div>
                <p className="mt-2 text-sm leading-7 text-white/78">像首页轮播/焦点位的简化版，用于承接专题情绪和论坛运营内容。</p>
              </div>
            ))}
          </div>
        </div>
        <div className="glass rounded-[32px] p-6 md:p-7">
          <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">Trending Search</div>
          <div className="mt-4 space-y-3">
            {['#高分动作新作', '#开黑不吵架', '#适合截图分享', '#轻策略别太肝', '#剧情好到想安利朋友'].map((item, index) => (
              <div key={item} className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">
                <div className="text-sm text-white/86">{index + 1}. {item}</div>
                <div className="text-xs text-soft">上升中</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-16 grid gap-10 md:mt-20 lg:grid-cols-2 lg:gap-12">
        {columns.map((column) => (
          <div key={column.title} className="glass rounded-[32px] p-7 md:p-9">
            <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">专题推荐</div>
            <h2 className="mt-3 text-3xl font-semibold">{column.title}</h2>
            <div className="mt-6 space-y-4">
              {column.items.map(([title, text], index) => (
                <div key={title} className="rounded-3xl border border-white/8 bg-white/[0.03] p-5">
                  <div className="text-xs uppercase tracking-[0.3em] text-white/42">0{index + 1}</div>
                  <div className="mt-2 text-xl font-semibold">{title}</div>
                  <p className="mt-2 text-sm leading-7 text-soft">{text}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </section>

      <section className="mt-16">
        <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="text-sm font-medium uppercase tracking-[0.32em] text-emerald-300/88">Recommended Feed</div>
            <div className="mt-3 text-2xl font-semibold">继续往下刷：游戏卡片流</div>
          </div>
          <div className="text-sm text-soft">这里保留稳定卡片流，确保预览与原型可读性不被“花哨”压垮。</div>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          {games.map((game) => (
            <GameCard key={game.slug} game={game} compact />
          ))}
        </div>
      </section>

      <section className="mt-16 glass rounded-[32px] p-7 md:mt-20 md:p-9">
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
