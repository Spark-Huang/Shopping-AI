from crawler.dangdang import parse_products, search_url


def test_parse_products_extracts_real_catalog_fields():
    html = """
    <li id="294857">
      <p class="name"><a title="Stainless Thermos Cup" href="//product.dangdang.com/294857.html">Stainless Thermos Cup</a></p>
      <p class="price"><span class="price_n">¥69.00</span></p>
      <div class="pic"><img data-original="//img.example-cdn.local/1.jpg" src="//img.example-cdn.local/1.jpg"/></div>
    </li>
    """
    products = parse_products(html, "thermos cup")
    assert products[0].name == "Stainless Thermos Cup"
    assert products[0].url == "https://product.dangdang.com/294857.html"
    assert products[0].price == 69.0
    assert products[0].image == "https://img.example-cdn.local/1.jpg"


def test_search_url_encodes_gbk_spaces():
    assert "key=%B1%A3%CE%C2%B1%AD" in search_url("保温杯")
