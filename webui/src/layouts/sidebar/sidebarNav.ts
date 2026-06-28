import {
  LayoutDashboard,
  MessageCircle,
  Plug,
  Puzzle,
  ScrollText,
  Settings,
  Store,
} from "@lucide/vue";
import type { Component } from "vue";

export interface NavLeaf {
  title: string;
  icon: Component;
  to?: { name: string };
  href?: string;
  external?: boolean;
}

export interface NavChild {
  title: string;
  to: { name: string };
}

export interface NavParent {
  title: string;
  icon: Component;
  children: NavChild[];
}

export type NavEntry = NavLeaf | NavParent;

export interface NavGroup {
  label?: string;
  items: NavEntry[];
}

export function isNavParent(item: NavEntry): item is NavParent {
  return "children" in item;
}

export const sidebarNav: NavGroup[] = [
  {
    label: "navGroup.overview",
    items: [
      { title: "nav.dashboard", icon: LayoutDashboard, to: { name: "dashboard" } },
    ],
  },
  {
    label: "navGroup.management",
    items: [
      { title: "nav.plugins", icon: Puzzle, to: { name: "plugins" } },
      { title: "nav.adapters", icon: Plug, to: { name: "adapters" } },
      { title: "nav.store", icon: Store, to: { name: "store" } },
    ],
  },
  {
    label: "navGroup.system",
    items: [
      { title: "nav.logs", icon: ScrollText, to: { name: "logs" } },
      {
        title: "nav.settings",
        icon: Settings,
        children: [
          { title: "nav.nonebot", to: { name: "settings-nonebot" } },
          { title: "nav.apeiria", to: { name: "settings-apeiria" } },
        ],
      },
    ],
  },
  {
    label: "navGroup.tools",
    items: [
      { title: "nav.webchat", icon: MessageCircle, to: { name: "webchat" } },
    ],
  },
];

export const routeTitleMap: Record<string, string> = Object.fromEntries(
  sidebarNav.flatMap((group) =>
    group.items.flatMap((item) =>
      isNavParent(item)
        ? item.children.map((child) => [child.to.name, child.title] as const)
        : item.to
          ? [[item.to.name, item.title] as const]
          : [],
    ),
  ),
);
