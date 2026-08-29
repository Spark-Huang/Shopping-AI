# Generate product photos for the 40 catalog expansion items (22 general + 18 Guizhou).
# Each image is a 1024-square e-commerce style shot; failures (<20KB) are retried up to 3 rounds.
$items = @(
  # --- 22 general expansion items ---
  @{ f = "web/public/images/products/classic-double-breasted-trench-coat.png"; p = "Professional e-commerce fashion product photography of a beige double-breasted trench coat with a removable belt and storm flap, displayed on an invisible mannequin against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/tailored-blazer.png"; p = "Professional e-commerce fashion product photography of a navy tailored blazer with notch lapels and flap pockets, displayed on an invisible mannequin against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/merino-knit-cardigan.png"; p = "Professional e-commerce fashion product photography of a cream fine-gauge merino wool cardigan with pearl buttons and ribbed trims, neatly folded against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/lightweight-down-vest.png"; p = "Professional e-commerce fashion product photography of a black lightweight quilted down vest with channels, displayed on an invisible mannequin against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/high-rise-straight-jeans.png"; p = "Professional e-commerce fashion product photography of indigo high-rise straight-leg jeans with a classic five-pocket cut, displayed flat on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/drapey-wide-leg-pants.png"; p = "Professional e-commerce fashion product photography of charcoal grey flowing wide-leg trousers with an elastic drawstring waist, displayed on an invisible mannequin against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/fleece-hoodie.png"; p = "Professional e-commerce fashion product photography of a heather grey fleece-lined hooded sweatshirt with drawstrings and a kangaroo pocket, displayed on an invisible mannequin against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/silk-ribbon-neck-blouse.png"; p = "Professional e-commerce fashion product photography of a champagne silk blouse with a ribbon-tie bow neckline and long sleeves, displayed on an invisible mannequin against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/linen-short-sleeve-shirt.png"; p = "Professional e-commerce fashion product photography of an oat-colored French linen short-sleeve shirt with a chest patch pocket and natural texture, displayed on an invisible mannequin against a clean white studio background, realistic" },
  @{ f = "web/public/images/products/wool-turtleneck-base-layer.png"; p = "Professional e-commerce fashion product photography of a fitted black wool-blend turtleneck base layer with fine ribbing, displayed on an invisible mannequin against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/vintage-martin-boots.png"; p = "Professional e-commerce product photography of a pair of brown vintage round-toe lace-up leather boots with chunky soles and side eyelets, on a clean white studio background, soft even lighting, realistic, high detail" },
  @{ f = "web/public/images/products/canvas-low-top-sneakers.png"; p = "Professional e-commerce product photography of a pair of classic white low-top canvas sneakers with vulcanized rubber soles, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/penny-loafers.png"; p = "Professional e-commerce product photography of a pair of black polished leather penny loafers with horsebit hardware and slim soles, on a clean white studio background, soft even lighting, realistic, high detail" },
  @{ f = "web/public/images/products/wool-lined-snow-boots.png"; p = "Professional e-commerce product photography of a pair of tan suede winter snow boots with plush wool lining and rugged lugged soles, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/woven-flat-sandals.png"; p = "Professional e-commerce product photography of a pair of hand-woven leather flat sandals with braided straps and cork footbeds, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/nylon-belt-bag.png"; p = "Professional e-commerce product photography of a black lightweight nylon waist bag with multiple zip compartments and an adjustable strap, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/leather-clutch-bag.png"; p = "Professional e-commerce product photography of a cognac brown full-grain leather clutch bag with hand-burnished edges and card slots, on a clean white studio background, soft even lighting, realistic, high detail" },
  @{ f = "web/public/images/products/wide-brim-straw-hat.png"; p = "Professional e-commerce product photography of a natural raffia straw wide-brim sun hat with a black grosgrain ribbon band, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/wool-check-scarf.png"; p = "Professional e-commerce product photography of a cozy plaid wool scarf in soft grey and cream checks with hand-knotted fringe, elegantly folded on a clean white background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/freshwater-pearl-bracelet.png"; p = "Professional e-commerce jewelry product photography of a white freshwater pearl bracelet with 6mm round pearls and a sterling silver clasp, macro shot on a clean white background, soft reflective lighting, realistic" },
  @{ f = "web/public/images/products/cubic-zirconia-pendant-necklace.png"; p = "Professional e-commerce jewelry product photography of a sparkling square cubic zirconia pendant necklace on a delicate silver chain, macro shot on a clean white background, soft reflective lighting, realistic" },
  @{ f = "web/public/images/products/baroque-pearl-earrings.png"; p = "Professional e-commerce jewelry product photography of a pair of baroque irregular freshwater pearl drop earrings with sterling silver hooks, macro shot on a clean white background, soft reflective lighting, realistic" },
  # --- 18 Guizhou expansion items ---
  @{ f = "web/public/images/products/guizhou/dafang-lacquer-food-box.png"; p = "Professional e-commerce product photography of a Chinese Yi ethnic lacquerware tiered round food box from Dafang, black red and yellow lacquer with subtle engraved floral patterns, glossy lacquer surface, on a clean white background, soft reflective lighting, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/zhijin-sand-pottery-teaset.png"; p = "Professional e-commerce product photography of rustic unglazed dark clay sand pottery tea set with teapot and cups, matte grey-black earthenware with a hand-thrown texture, on a clean white background, soft lighting, realistic" },
  @{ f = "web/public/images/products/guizhou/anshun-dixi-opera-mask.png"; p = "Professional e-commerce product photography of a carved and painted Chinese Dixi opera wooden mask from Anshun, dramatic general face in bold red black and gold, standing display piece, on a clean white background, soft lighting, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/sizhou-stone-inkstone.png"; p = "Professional e-commerce product photography of a traditional Chinese stone inkstone with carved dragon relief in dark slate with golden speckles, complete with lid, on a clean white background, soft lighting, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/miao-lusheng-reed-pipe.png"; p = "Professional e-commerce product photography of a traditional Miao ethnic lusheng reed pipe instrument, six bamboo pipes bound to a carved wooden base with copper reeds, standing upright, on a clean white background, soft lighting, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/shui-horsetail-embroidery-pouch.png"; p = "Professional e-commerce product photography of a Shui ethnic horsetail embroidery pouch, raised glossy silk embroidery in red green and gold on dark indigo fabric, small drawstring bag, on a clean white background, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/miao-silver-horn-headdress.png"; p = "Professional e-commerce jewelry product photography of a Miao ethnic silver horn headdress, tall curved silver horns with intricate engraved patterns on a silver band, on a clean white studio background, soft reflective lighting, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/dong-cloth-scarf.png"; p = "Professional e-commerce product photography of a Dong ethnic indigo glossy cloth scarf with a subtle bronze-purple sheen and fine woven stripes, elegantly draped on a clean white background, soft lighting, realistic" },
  @{ f = "web/public/images/products/guizhou/zunyi-egg-cake.png"; p = "Professional food photography of traditional Chinese Zunyi egg cakes, golden round sponge pastries with glossy browned tops arranged on a white ceramic plate, soft warm lighting, appetizing, realistic" },
  @{ f = "web/public/images/products/guizhou/weining-buckwheat-pastry.png"; p = "Professional food photography of Weining buckwheat pastries, golden flat tart-like buckwheat cakes with crimped edges and a sweet bean filling, arranged on a rustic wooden board, soft lighting, appetizing, realistic" },
  @{ f = "web/public/images/products/guizhou/xiuwen-kiwi-fruit.png"; p = "Professional food product photography of fresh Xiuwen kiwifruits with fuzzy brown skin, one cut in half showing bright green flesh with black seeds, in a small wooden crate, on a clean rustic background, appetizing, realistic" },
  @{ f = "web/public/images/products/guizhou/majiang-dried-blueberries.png"; p = "Professional food product photography of dried blueberries piled in a small wooden scoop with a few fresh blueberries beside, deep purple wrinkled dried berries, on a clean white background, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/cili-fruit-preserve.png"; p = "Professional food product photography of candied cili (Rosa roxburghii) fruit preserves, golden translucent candied fruits in a small ceramic dish, on a clean rustic wooden background, appetizing, realistic" },
  @{ f = "web/public/images/products/guizhou/qingyan-fermented-tofu.png"; p = "Professional food product photography of Chinese fermented tofu cubes coated in red chili powder in a glass jar with a wooden spoon, on a clean rustic background, appetizing, realistic" },
  @{ f = "web/public/images/products/guizhou/zunyi-huangba-cake.png"; p = "Professional food photography of Zunyi huangba, golden steamed sticky rice cakes wrapped in green leaves, one sliced open showing glossy golden rice texture, on a bamboo steamer, soft warm lighting, appetizing, realistic" },
  @{ f = "web/public/images/products/guizhou/zhijin-bamboo-fungus.png"; p = "Professional food product photography of dried bamboo fungus with white lattice net skirts standing in a small glass bowl, on a clean white background with a linen cloth, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/leishan-silver-ball-tea.png"; p = "Professional tea product photography of Leishan silver ball tea, round compressed green tea balls beside a glass cup of steeped yellow-green liquor with one ball unfurling, clean minimal styling, realistic" },
  @{ f = "web/public/images/products/guizhou/dong-liquor.png"; p = "Professional liquor product photography of a Chinese baijiu bottle of Dong liquor, elegant clear glass bottle with a red and gold label, on a clean white background with soft reflections, realistic, high detail" }
)

function Invoke-GenImage {
  param($it)
  $encoded = [uri]::EscapeDataString($it.p)
  $url = "https://console.enterprise.trae.cn/api/ide/v1/text_to_image?prompt=$encoded&image_size=square_hd"
  curl.exe -s -L --max-time 180 -o $it.f $url
  if (Test-Path $it.f) {
    return (Get-Item $it.f).Length
  }
  return 0
}

$ok = 0
$fail = 0
$pending = @()
foreach ($it in $items) {
  $size = Invoke-GenImage $it
  if ($size -gt 20000) {
    $ok++
    Write-Output "OK   $($it.f) ($([math]::Round($size/1KB))KB)"
  } else {
    $fail++
    $pending += $it
    Write-Output "FAIL $($it.f) ($size bytes)"
  }
}

# Retry failures for up to 3 more rounds.
for ($round = 1; $round -le 3 -and $pending.Count -gt 0; $round++) {
  Write-Output "RETRY round $round for $($pending.Count) item(s)"
  $still = @()
  foreach ($it in $pending) {
    $size = Invoke-GenImage $it
    if ($size -gt 20000) {
      $ok++
      $fail--
      Write-Output "OK   $($it.f) after retry ($([math]::Round($size/1KB))KB)"
    } else {
      $still += $it
    }
  }
  $pending = $still
  if ($pending.Count -gt 0 -and $round -lt 3) {
    Start-Sleep -Seconds 5
  }
}

Write-Output "DONE ok=$ok fail=$fail"
if ($pending.Count -gt 0) {
  Write-Output "REMAINING FAILURES:"
  foreach ($it in $pending) { Write-Output "  $($it.f)" }
}
