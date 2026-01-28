from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import sys

# Default paths
html_path = sys.argv[1] if len(sys.argv) > 1 else r'D:/Claude/MimicVirgo/sandiego_test.html'
screenshot_path = sys.argv[2] if len(sys.argv) > 2 else r'D:/Claude/MimicVirgo/screenshot_popup.png'

options = Options()
options.add_argument('--headless')
options.add_argument('--window-size=1920,1400')
options.add_argument('--disable-gpu')

driver = webdriver.Chrome(options=options)

file_url = 'file:///' + html_path.replace('\\', '/')
print(f'Loading: {file_url}')
driver.get(file_url)
time.sleep(3)

# Find a site with both percentile data and time series data
try:
    js_code = """
    var gd = document.getElementsByClassName('js-plotly-plot')[0];
    if (gd && gd.data && gd.data[0] && gd.data[0].customdata) {
        var sites = gd.data[0].customdata;

        // Find a site with BOTH percentile data AND time series
        for (var i = 0; i < sites.length; i++) {
            var site = sites[i];
            var hasPct = site.pct_lowest !== null && site.pct_highest !== null;
            var hasTs = MapState.siteTimeSeries[site.site_no] && MapState.siteTimeSeries[site.site_no].dates && MapState.siteTimeSeries[site.site_no].dates.length > 0;

            if (hasPct && hasTs) {
                showMarkerPopup(site.site_no, site);
                return site.site_no;
            }
        }
        return null;
    }
    return null;
    """
    result = driver.execute_script(js_code)
    print(f'Opened popup for: {result}')
    time.sleep(3)

    # Expand popup to show all content
    driver.execute_script("""
        var popup = document.getElementById('markerPopup');
        var body = document.getElementById('popupBody');
        if (popup && body) {
            popup.style.width = '800px';
            popup.style.height = 'auto';
            popup.style.maxHeight = 'none';
            popup.style.top = '20px';
            popup.style.left = '50%';
            popup.style.transform = 'translateX(-50%)';
            body.style.maxHeight = 'none';
            body.style.overflow = 'visible';
        }
    """)
    time.sleep(1)

except Exception as e:
    print(f'Error: {e}')

driver.save_screenshot(screenshot_path)
print(f'Screenshot saved: {screenshot_path}')
driver.quit()
