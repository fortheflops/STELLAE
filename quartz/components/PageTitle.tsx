import { pathToRoot } from "../util/path"
import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { classNames } from "../util/lang"
import { i18n } from "../i18n"

const PageTitle: QuartzComponent = ({ fileData, cfg, displayClass }: QuartzComponentProps) => {
  const title = cfg?.pageTitle ?? i18n(cfg.locale).propertyDefaults.title
  const baseDir = pathToRoot(fileData.slug!)

  const splitTitle = (title: string) => {
    if (title === "MEZZALUNA") {
      return ["MEZZA", "LUNA"]
    }
    // For other titles, split by words
    const words = title.split(" ")
    const mid = Math.ceil(words.length / 2)
    const firstHalf = words.slice(0, mid).join(" ")
    const secondHalf = words.slice(mid).join(" ")
    return [firstHalf, secondHalf]
  }

  const [firstHalf, secondHalf] = splitTitle(title)

  return (
    <h2 class={classNames(displayClass, "page-title")}>
      <a href={baseDir}>
        <span class="title-text">
          <span class="first-half">{firstHalf}</span>
          <span class="second-half">{secondHalf}</span>
        </span>
      </a>
    </h2>
  )
}

PageTitle.css = `
.page-title {
  font-size: 1.75rem;
  margin: 0;
}

.page-title a {
  display: block;
}

.page-title .title-text span {
  display: inline-block; /* Default, for desktop */
}

/* Media query for mobile devices */
@media (max-width: 445px) {
  .page-title .title-text .first-half {
    /* Prevent wrapping within the first half */
    white-space: nowrap;
  }
  .page-title .title-text .second-half {
    display: block; /* Force a line break before the second half */
  }
}

/* Media query for very small mobile devices */
@media (max-width: 320px) { 
    .page-title {
      font-size: 1.5rem;
    }
}
`

export default (() => PageTitle) satisfies QuartzComponentConstructor