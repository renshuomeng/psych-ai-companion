export default function AccessDenied() {
  return (
    <section className="page-stack access-denied-page">
      <div className="section-heading">
        <span className="eyebrow">Access Denied</span>
        <h1>无权访问</h1>
        <p>当前账号不能打开这个功能。请切换到具备相应角色的账号后再试。</p>
      </div>
    </section>
  );
}
