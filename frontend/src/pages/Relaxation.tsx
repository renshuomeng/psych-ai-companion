export default function Relaxation() {
  return (
    <section className="page-stack">
      <div className="section-heading">
        <span className="eyebrow">Relaxation</span>
        <h1>呼吸训练</h1>
        <p>一个可用于演示的简单放松练习卡片。</p>
      </div>

      <section className="breathing-panel">
        <div className="breathing-circle">
          <span>呼吸</span>
        </div>
        <div>
          <h2>3 分钟呼吸练习</h2>
          <p>吸气 4 秒，停顿 2 秒，呼气 6 秒。跟随圆形节奏重复 5 轮。</p>
          <ol className="plain-list">
            <li>找一个相对安静的位置坐好。</li>
            <li>把注意力放在鼻尖或胸口的起伏上。</li>
            <li>如果分心了，只需要温和地把注意力带回来。</li>
          </ol>
        </div>
      </section>
    </section>
  );
}
