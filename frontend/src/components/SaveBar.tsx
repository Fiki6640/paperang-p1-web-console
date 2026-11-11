import { Button } from "@heroui/react";
import { Loader2, RotateCcw, Save } from "lucide-react";

/**
 * 设置页 sticky 保存栏:仅在有未保存修改时出现(桌面吸底、移动端在底栏上方)。
 */
export default function SaveBar({
  visible,
  saving,
  onSave,
  onReset,
}: {
  visible: boolean;
  saving: boolean;
  onSave: () => void;
  onReset: () => void;
}) {
  if (!visible) return null;
  return (
    <div className="fixed inset-x-0 bottom-14 z-20 border-t border-default-200 bg-content1/95 px-4 py-3 backdrop-blur lg:bottom-0 lg:pl-60">
      <div className="mx-auto flex max-w-4xl items-center justify-between gap-3">
        <span className="text-sm text-foreground/70">有未保存的修改</span>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onPress={onReset} isDisabled={saving}>
            <RotateCcw size={15} aria-hidden />
            撤销修改
          </Button>
          <Button size="sm" onPress={onSave} isPending={saving}>
            {!saving && <Save size={15} aria-hidden />}
            保存
          </Button>
        </div>
      </div>
    </div>
  );
}

/** 表单里的小号 loading 图标(Button isLoading 自带 spinner,这里用于自定义按钮) */
export function Spinner({ size = 16 }: { size?: number }) {
  return <Loader2 size={size} className="animate-spin" aria-hidden />;
}
