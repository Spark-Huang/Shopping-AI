# Generate product photos for the 20 new Guizhou catalog items.
$items = @(
  @{ f = "web/public/images/products/guizhou/miao-silver-butterfly-pendant.png"; p = "Professional e-commerce jewelry product photography of a handcrafted Miao ethnic silver butterfly pendant with intricate filigree wirework wings, macro shot on a clean white background, soft reflective lighting, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/miao-silver-twisted-collar.png"; p = "Professional e-commerce jewelry product photography of a traditional Miao ethnic silver torc necklace made of multiple twisted silver strands, on a clean white studio background, soft reflective lighting, realistic" },
  @{ f = "web/public/images/products/guizhou/shui-horsetail-embroidery-apron.png"; p = "Professional e-commerce product photography of a Shui ethnic horsetail embroidery apron with raised glossy geometric dragon patterns in red green and gold thread on dark indigo fabric, displayed flat on a clean white background, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/dong-embroidered-baby-hat.png"; p = "Professional e-commerce product photography of a Dong ethnic embroidered baby hat in red fabric with colorful floral silk thread embroidery, silver ornaments and small tassels on top, on a clean white background, realistic" },
  @{ f = "web/public/images/products/guizhou/miao-batik-scarf.png"; p = "Professional e-commerce product photography of an indigo blue Miao batik scarf with white spiral and bird wax-resist patterns and fine crackle texture, elegantly draped on a clean white background, realistic" },
  @{ f = "web/public/images/products/guizhou/shiqiao-paper-notebook.png"; p = "Professional e-commerce product photography of a handmade flower-embedded craft paper notebook with cream colored cover embedded with real dried flowers and leaves, on a clean white background, soft natural lighting, realistic" },
  @{ f = "web/public/images/products/guizhou/yazhou-pottery-teaset.png"; p = "Professional e-commerce product photography of a handmade Chinese pottery tea set with emerald green glaze teapot and cups, rustic folk ceramic style, on a clean white background, soft lighting, realistic" },
  @{ f = "web/public/images/products/guizhou/yuping-flute.png"; p = "Professional e-commerce product photography of a traditional Chinese bamboo vertical flute with carved calligraphy on the body, lying diagonally on a clean white background, soft lighting, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/miao-silver-earrings.png"; p = "Professional e-commerce jewelry product photography of a pair of handcrafted Miao ethnic silver dangle earrings with woven wirework and small chime pendants, macro shot on a clean white background, reflective lighting, realistic" },
  @{ f = "web/public/images/products/guizhou/zunyi-mutton-rice-noodle.png"; p = "Professional food photography of a bowl of Guizhou Zunyi mutton rice noodles in clear amber broth with sliced mutton, cilantro and chili oil, served in a ceramic bowl on wooden table, appetizing, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/huaxi-beef-noodle.png"; p = "Professional food photography of a bowl of Guiyang Huaxi beef rice noodle soup with tender sliced beef, clear golden broth, pickled beans and chili on top, on a rustic wooden table, appetizing, realistic" },
  @{ f = "web/public/images/products/guizhou/guizhou-hu-lajiao.png"; p = "Professional food product photography of Guizhou charcoal-roasted chili flakes hu lajiao in a small ceramic dish, deep red coarse crushed chili powder with smoky aroma, on a clean rustic wooden background, realistic" },
  @{ f = "web/public/images/products/guizhou/dushan-pickled-vegetable.png"; p = "Professional food product photography of Dushan pickled mustard greens suan caicai in a glass jar, glossy fermented vegetables in red chili brine, on a clean white background, appetizing, realistic" },
  @{ f = "web/public/images/products/guizhou/qingyan-rose-candy.png"; p = "Professional food photography of traditional Chinese rose candy pieces, pale golden crispy malt sugar candies filled with candied rose petals, arranged on a white ceramic plate, soft lighting, realistic" },
  @{ f = "web/public/images/products/guizhou/guizhou-smoked-bacon.png"; p = "Professional food product photography of Chinese wood-smoked cured pork belly la rou with deep reddish-brown marbled slices, tied with twine, on a rustic wooden board, realistic, high detail" },
  @{ f = "web/public/images/products/guizhou/congjiang-glutinous-rice.png"; p = "Professional food product photography of premium glutinous rice kernels he xiang nuo in a bamboo scoop over a cloth sack, plump pearl-white grains, on a clean rustic background, realistic" },
  @{ f = "web/public/images/products/guizhou/meitan-cuiya-tea.png"; p = "Professional tea product photography of Meitan Cuiya green tea, flat sparrow-tongue shaped green tea leaves in a white porcelain dish beside a brewed glass cup with bright yellow-green liquor, clean minimal styling, realistic" },
  @{ f = "web/public/images/products/guizhou/guiding-cloud-tea.png"; p = "Professional tea product photography of curly dark green Guiding Yunwu tea leaves scattered beside a brewing glass teapot with golden-green liquor and mountain mist backdrop, elegant, realistic" },
  @{ f = "web/public/images/products/guizhou/puan-black-tea.png"; p = "Professional tea product photography of Puan Hong black tea, tightly twisted dark amber tea leaves in a linen pouch beside a white gaiwan cup with bright orange-red liquor, warm lighting, realistic" },
  @{ f = "web/public/images/products/guizhou/guizhou-emerald-tea.png"; p = "Professional tea product photography of Guizhou Emerald green tea, dark green tightly rolled pearl-shaped tea granules in a wooden scoop beside a brewed glass with yellow-green liquor, clean minimal styling, realistic" }
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
