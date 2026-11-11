import type { ReactNode } from "react";
/** 页面头部说明区:描述 + 右侧动作位(页面标题已上移到顶栏) */
export default function PageHeader({
  description,
  actions,
}: {
  description?: string;
  actions?: ReactNode;
}) {
  if (!description && !actions) return null;
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      {description ? <p className="text-sm text-foreground/60">{description}</p> : <span />}
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}
