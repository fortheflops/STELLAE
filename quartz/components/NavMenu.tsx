import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"

export default ((userOpts?: Options) => {
  function NavMenu(props: QuartzComponentProps) {
    return (
      <div class="navmenu">
        <p> <a href="/Appetizers">Appetizers</a></p>
        <p> <a href="/Beverages">Beverages</a></p>
        <p> <a href="/Bread">Bread</a></p>
        <p> <a href="/Desserts">Desserts</a></p>
        <p> <a href="/Entrees">Entrees</a></p>
        <p> <a href="/Salads">Salads</a></p>
        <p> <a href="/Sauces">Sauces</a></p>
	<p> <a href="/Sides">Sides</a></p>
        <p> <a href="/Snacks">Snacks</a></p>
        <p> <a href="/Soups">Soups</a></p>
        <p> <a href="/Other">Other</a></p>
      </div>
    )
  }
 
  return NavMenu
}) satisfies QuartzComponentConstructor
