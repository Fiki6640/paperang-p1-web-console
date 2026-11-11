/** 主题切换: .dark class + localStorage 记忆 + 跟随系统 */

export type ThemeChoice = "light" | "dark" | "system";

const KEY = "paperang-theme";

export function getStoredTheme(): ThemeChoice {
  const v = localStorage.getItem(KEY);
  return v === "light" || v === "dark" ? v : "system";
}

function apply(choice: ThemeChoice) {
  const dark =
    choice === "dark" ||
    (choice === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function setTheme(choice: ThemeChoice) {
  localStorage.setItem(KEY, choice);
  apply(choice);
}

/** 跟随系统变化(仅当用户选择 system 时生效);返回清理函数 */
export function watchSystemTheme(): () => void {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const onChange = () => {
    if (getStoredTheme() === "system") apply("system");
  };
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}
