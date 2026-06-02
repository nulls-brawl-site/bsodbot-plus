import { Menu, Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ThreadHeaderProps {
  title: string;
  onToggleSidebar: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  hideSidebarToggleOnDesktop?: boolean;
  minimal?: boolean;
}

export function ThreadHeader({
  title,
  onToggleSidebar,
  theme,
  onToggleTheme,
  hideSidebarToggleOnDesktop = false,
  minimal = false,
}: ThreadHeaderProps) {
  const { t } = useTranslation();
  if (minimal) {
    return (
      <div className="relative z-10 flex h-14 items-center justify-between gap-3 px-4 py-3 bg-background/80 backdrop-blur-md border-b border-border/40">
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("thread.header.toggleSidebar")}
          onClick={onToggleSidebar}
          className={cn(
            "h-10 w-10 rounded-full text-muted-foreground hover:bg-accent/50 hover:text-foreground active:scale-95 transition-all",
            hideSidebarToggleOnDesktop && "lg:hidden",
          )}
        >
          <Menu className="h-5 w-5" />
        </Button>
        <ThemeButton
          theme={theme}
          onToggleTheme={onToggleTheme}
          label={t("thread.header.toggleTheme")}
          className="ml-auto"
        />
      </div>
    );
  }

  return (
    <div className="relative z-10 flex h-14 items-center justify-between gap-3 px-4 py-3 bg-background/80 backdrop-blur-md border-b border-border/40">
      <div className="relative flex min-w-0 items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("thread.header.toggleSidebar")}
          onClick={onToggleSidebar}
          className={cn(
            "h-10 w-10 rounded-full text-muted-foreground hover:bg-accent/50 hover:text-foreground active:scale-95 transition-all",
            hideSidebarToggleOnDesktop && "lg:hidden",
          )}
        >
          <Menu className="h-5 w-5" />
        </Button>
        <div className="flex min-w-0 items-center rounded-full bg-secondary/50 px-4 py-1.5 text-[13px] font-semibold text-secondary-foreground">
          <span className="max-w-[min(50vw,24rem)] truncate">{title}</span>
        </div>
      </div>

      <ThemeButton
        theme={theme}
        onToggleTheme={onToggleTheme}
        label={t("thread.header.toggleTheme")}
        className="ml-auto shrink-0"
      />

      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-full h-4" />
    </div>
  );
}

function ThemeButton({
  theme,
  onToggleTheme,
  label,
  className,
}: {
  theme: "light" | "dark";
  onToggleTheme: () => void;
  label: string;
  className?: string;
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={label}
      onClick={onToggleTheme}
      className={cn(
        "h-10 w-10 rounded-full text-muted-foreground/85 hover:bg-accent/50 hover:text-foreground active:scale-95 transition-all",
        className,
      )}
    >
      {theme === "dark" ? (
        <Sun className="h-5 w-5 text-amber-400" />
      ) : (
        <Moon className="h-5 w-5 text-indigo-600" />
      )}
    </Button>
  );
}

function ThemeButton({
  theme,
  onToggleTheme,
  label,
  className,
}: {
  theme: "light" | "dark";
  onToggleTheme: () => void;
  label: string;
  className?: string;
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={label}
      onClick={onToggleTheme}
      className={cn(
        "h-8 w-8 rounded-full text-muted-foreground/85 hover:bg-accent/40 hover:text-foreground",
        className,
      )}
    >
      {theme === "dark" ? (
        <Sun className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
    </Button>
  );
}
