import { PageLayout, SharedLayout } from "./quartz/cfg"
import * as Component from "./quartz/components"

// components shared across all pages
export const sharedPageComponents: SharedLayout = {
  head: Component.Head(),
  header: [],
  afterBody: [
    Component.Comments({
      provider: 'giscus',
      options: {
        // from data-repo
        repo: 'fortheflops/STELLAE',
        // from data-repo-id
        repoId: 'R_kgDONT3VDQ',
        // from data-category
        category: 'Announcements',
        // from data-category-id
        categoryId: 'DIC_kwDONT3VDc4Cl77q',
      }
    }),
  ],
  footer: Component.Footer({
    links: {
      GitHub: "https://github.com/jackyzha0/quartz",
      "Discord Community": "https://discord.gg/cRFFHYye7t",
    },
  }),
}

// components for pages that display a single page (e.g. a single note)
export const defaultContentPageLayout: PageLayout = {
  beforeBody: [
    Component.ConditionalRender({
      component: Component.Breadcrumbs(),
      condition: (page) => page.fileData.slug !== "index",
    }),
    Component.ArticleTitle(),
    Component.ContentMeta(),
    Component.TagList(),
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Search(),
    Component.Darkmode(),
    Component.DesktopOnly(Component.NavMenu()),
  ],
  right: [
    Component.DesktopOnly(Component.Graph(), Component.TableOfContents()),
    Component.Backlinks(),
    Component.RecentNotes({
      title: "Recently Added Recipes",
      limit: 5,
      filter: (f) => f.slug !== "index" && !f.slug?.startsWith("tags/"),
    }),
  ],
}

// components for pages that display lists of pages  (e.g. tags or folders)
export const defaultListPageLayout: PageLayout = {
  beforeBody: [
    Component.Breadcrumbs(),
    Component.ArticleTitle(),
    Component.ContentMeta()
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Search(),
    Component.Darkmode(),
    Component.DesktopOnly(Component.NavMenu()),
  ],
  right: [
    Component.DesktopOnly(Component.Graph(), Component.TableOfContents()),
    Component.Backlinks(),
    Component.RecentNotes({
      title: "Recently Added Recipes",
      limit: 5,
      filter: (f) => f.slug !== "index" && !f.slug?.startsWith("tags/"),
    }),
  ],
}