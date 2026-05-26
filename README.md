# Falcon Forecast

A multi-factor raptor migration scoring system for 8 monitoring sites across China. Combines Open-Meteo weather data, eBird observations, terrain dynamics, and seasonal phenology to produce daily 0-100 migration suitability scores.

## How It Works

The V9 model calculates an hourly score (0-100) for each site based on:

| Factor | Weight | Description |
|--------|--------|-------------|
| Wind lift | 15 pts | Speed in optimal 15-45 kts band, site-adaptive thresholds |
| Ridge orthogonal lift | 15 pts | Wind vector perpendicular to ridge orientation |
| Thermal dynamics | 10 pts | Lifted Index (LI) from 850/925 hPa layers |
| Inversion penalty | -5/C | 850-925 hPa temperature delta |
| Cold front bonus | +20 pts | 24h temp drop >5C + pressure rise |
| Phenology peak | x0.3-1.6 | Month/decade matrix per site and season |
| Historical abundance | x1.0-1.85 | Site-specific raptor density weights |
| eBird multiplier | x0.8-1.2 | Recent observation spatial correction |
| Juvenile dispersal | +8 pts | Autumn coastal bonus |

**Rating scale:**
- 88-100: Must-see migration event
- 75-87: Highly recommended
- 60-74: Worth visiting
- 40-59: Moderate conditions
- 0-39: Poor conditions

## Monitoring Sites

| Site | Type | Location | Coordinates |
|------|------|----------|-------------|
| Du Tong Yan (都统岩) | Inland ridge | Chongzhou, Sichuan | 30.76N, 103.42E |
| Long Quan Shan (龙泉山) | Inland ridge | Chengdu, Sichuan | 30.56N, 104.31E |
| Yao Shan TV Tower (尧山电视台) | Karst ridge | Guilin, Guangxi | 25.30N, 110.38E |
| Guan Tou Ling (冠头岭) | Cape bottleneck | Beihai, Guangxi | 21.45N, 109.05E |
| Jiu Long Shan (九龙山) | Coastal bottleneck | Pinghu, Zhejiang | 29.50N, 121.50E |
| Yu Yang Shan (渔洋山) | Lake-shore | Suzhou, Jiangsu | 31.20N, 120.40E |
| Nanhui Dongtan (南汇东滩) | Coastal corridor | Shanghai | 30.90N, 121.90E |
| Chongming Dongtan (崇明东滩) | Estuary wetland | Shanghai | 31.50N, 121.90E |

## Quick Start

### 1. Clone and install dependencies

```bash
git clone https://github.com/jasonzhouyu/falcon_forecast.git
cd falcon_forecast

pip install requests numpy openmeteo-requests requests-cache retry-requests python-dotenv matplotlib
```

### 2. Configure API key

Create a `.env` file:

```env
EBIRD_API_KEY=your_key_here
```

Get a free key at [ebird.org/api/keygen](https://ebird.org/api/keygen). The system works without it (eBird multiplier defaults to 1.0), but predictions are more accurate with real observation data.

### 3. Run a prediction

```bash
# Single site, today
python raptor_v9_runner.py

# All 8 sites, generate full HTML report
python raptor_v9_full_report.py

# All sites batch (console output)
python run_all_sites_v9.py
```

### 4. Daily automation (optional)

```bash
# Set up cron (6:00 AM Asia/Shanghai)
0 22 * * * cd /path/to/falcon_forecast && python3 send_raptor_v9_mail.py
```

Email delivery requires SMTP config in `send_raptor_v9_mail.py`.

## Project Structure

```
raptor_v9_runner.py        Core scoring engine (V9 model)
raptor_v9_full_report.py   HTML report generator with matplotlib charts
run_all_sites_v9.py        Batch runner for all 8 sites
send_raptor_v9_mail.py     Email distribution to subscribers
run_raptor_daily.py        Legacy daily workflow
daily_raptor_report.py     Simplified daily report
report_formatter.py        Report formatting utilities
raptor_species_expanded.py Species-specific parameters (25 raptors)
google_form_sync.py        Google Forms subscriber management
daily_task.sh              Cron entry point
cron-watchdog.sh           Cron health monitor
```

## Data Sources

- **[Open-Meteo](https://open-meteo.com/)** - Free weather API providing wind, temperature, pressure, cloud cover, precipitation at surface + pressure levels (850/925 hPa).
- **[eBird](https://ebird.org/)** - Recent raptor observations within 50km radius of each site. Requires free API key.

## Example Output

See [example_report.html](example_report.html) for a full daily report with hourly scores, 7-day trends, and observation strategies for all 8 sites.

## Migration Seasons

- **Spring**: March-May (peak: mid-April)
- **Autumn**: September-November (peak: mid-October)

Outside these windows the model returns low scores regardless of weather.

## License

MIT

## Contributing

Issues and PRs welcome. If you monitor a raptor site in China not listed here, open an issue with coordinates and ridge orientation - adding new sites is straightforward.
