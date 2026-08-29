# Generate high-quality product photos for the 29 non-Guizhou catalog items.
$items = @(
  @{ f = "web/public/images/products/everyday-canvas-tote.png"; p = "Professional e-commerce product photography of a durable natural tan cotton canvas tote bag with reinforced stitched handles and a zip closure, standing upright on a clean white studio background, soft even lighting, realistic, high detail" },
  @{ f = "web/public/images/products/compact-crossbody-bag.png"; p = "Professional e-commerce product photography of a lightweight black water-resistant crossbody bag with an adjustable strap and zip main compartment, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/structured-work-tote.png"; p = "Professional e-commerce product photography of an elegant black padded laptop tote bag with matte hardware and detachable organizer pouch, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/packable-travel-backpack.png"; p = "Professional e-commerce product photography of a grey 20-liter ripstop nylon travel backpack with a padded sleeve and water bottle pocket, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/polarized-aviator-sunglasses.png"; p = "Professional e-commerce product photography of silver-framed polarized aviator sunglasses with dark gradient lenses, on a clean white studio background, soft even lighting, realistic, high detail" },
  @{ f = "web/public/images/products/matte-round-sunglasses.png"; p = "Professional e-commerce product photography of matte black round acetate sunglasses with UV protection lenses, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/sport-shield-sunglasses.png"; p = "Professional e-commerce product photography of wraparound sport shield sunglasses with anti-slip nose bridge, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/bias-cut-midi-dress.png"; p = "Professional e-commerce fashion product photography of a fluid matte champagne satin bias-cut midi slip dress with adjustable straps, displayed on an invisible mannequin against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/cotton-shirt-dress.png"; p = "Professional e-commerce fashion product photography of a breathable beige organic cotton shirt dress with a removable belt and patch pockets, displayed on an invisible mannequin against a clean white studio background, realistic" },
  @{ f = "web/public/images/products/layered-knit-dress.png"; p = "Professional e-commerce fashion product photography of a soft cream knitted midi dress with a rounded neckline and tiered skirt, displayed on an invisible mannequin against a clean white studio background, realistic" },
  @{ f = "web/public/images/products/pleated-midi-skirt.png"; p = "Professional e-commerce fashion product photography of a lightweight sage green pleated midi skirt with an elastic waistband, displayed against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/denim-a-line-skirt.png"; p = "Professional e-commerce fashion product photography of an indigo rigid denim A-line midi skirt with front pockets, displayed against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/tailored-column-skirt.png"; p = "Professional e-commerce fashion product photography of a black high-waist tailored straight column skirt with concealed side zip, displayed against a clean white studio background, realistic" },
  @{ f = "web/public/images/products/merino-crew-sweater.png"; p = "Professional e-commerce fashion product photography of a fine-gauge light grey merino wool crewneck sweater with ribbed cuffs, neatly folded against a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/oxford-button-down-shirt.png"; p = "Professional e-commerce fashion product photography of a crisp white cotton oxford button-down shirt with a boxy fit and curved hem, neatly displayed against a clean white studio background, realistic" },
  @{ f = "web/public/images/products/ribbed-knit-top.png"; p = "Professional e-commerce fashion product photography of a beige stretch ribbed knit top with a mock neckline and long sleeves, displayed on an invisible mannequin against a clean white studio background, realistic" },
  @{ f = "web/public/images/products/silk-blend-camisole.png"; p = "Professional e-commerce fashion product photography of a matte champagne silk-blend camisole with adjustable straps and a draped neckline, displayed against a clean white studio background, realistic" },
  @{ f = "web/public/images/products/cushioned-running-shoes.png"; p = "Professional e-commerce product photography of a pair of white and blue neutral running shoes with breathable engineered mesh uppers and responsive foam soles, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/waterproof-hiking-shoes.png"; p = "Professional e-commerce product photography of a pair of brown lightweight waterproof hiking shoes with grippy outsoles and protective toe caps, on a clean white studio background, realistic" },
  @{ f = "web/public/images/products/leather-city-sneakers.png"; p = "Professional e-commerce product photography of a pair of minimalist white full-grain leather sneakers with tonal stitching and rubber cup soles, on a clean white studio background, realistic, high detail" },
  @{ f = "web/public/images/products/suede-ankle-boots.png"; p = "Professional e-commerce product photography of a pair of tan suede ankle boots with a side zip and stacked low heel, on a clean white studio background, soft even lighting, realistic" },
  @{ f = "web/public/images/products/ballet-flats.png"; p = "Professional e-commerce product photography of a pair of blush pink foldable ballet flats with elastic trim and rubber soles, on a clean white studio background, realistic" },
  @{ f = "web/public/images/products/brushed-cuff-bracelet.png"; p = "Professional e-commerce jewelry product photography of an adjustable brushed silver metal cuff bracelet with a sculptural shape, macro shot on a clean white background, soft reflective lighting, realistic" },
  @{ f = "web/public/images/products/braided-cord-bracelet.png"; p = "Professional e-commerce jewelry product photography of a navy braided cord bracelet with a sliding knot closure and a brushed metal accent bead, macro shot on a clean white background, realistic" },
  @{ f = "web/public/images/products/pearl-stud-earrings.png"; p = "Professional e-commerce jewelry product photography of a pair of white freshwater pearl stud earrings with silver posts, macro shot on a clean white background, soft reflective lighting, realistic" },
  @{ f = "web/public/images/products/geometric-drop-earrings.png"; p = "Professional e-commerce jewelry product photography of a pair of matte gold geometric drop earrings with hypoallergenic hooks, macro shot on a clean white background, realistic" },
  @{ f = "web/public/images/products/layered-chain-necklace.png"; p = "Professional e-commerce jewelry product photography of a two-layer gold chain necklace with an adjustable clasp, elegantly arranged on a clean white background, soft reflective lighting, realistic" },
  @{ f = "web/public/images/products/simple-pendant-necklace.png"; p = "Professional e-commerce jewelry product photography of a minimalist silver pendant necklace with an eighteen-inch cable chain, on a clean white background, soft reflective lighting, realistic" },
  @{ f = "web/public/images/products/beaded-choker.png"; p = "Professional e-commerce jewelry product photography of a hand-finished colorful glass bead choker necklace with a soft cord backing, on a clean white background, realistic" }
)

$ok = 0; $fail = 0
foreach ($it in $items) {
  $encoded = [uri]::EscapeDataString($it.p)
  $url = "https://console.enterprise.trae.cn/api/ide/v1/text_to_image?prompt=$encoded&image_size=square_hd"
  curl.exe -s -L --max-time 180 -o $it.f $url
  $size = (Get-Item $it.f).Length
  if ($size -gt 20000) {
    $ok++
    Write-Output "OK   $($it.f) ($([math]::Round($size/1KB))KB)"
  } else {
    $fail++
    Write-Output "FAIL $($it.f) ($size bytes)"
  }
}
Write-Output "DONE ok=$ok fail=$fail"
