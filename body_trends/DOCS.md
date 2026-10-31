# Body Trends

Local trend analysis of body measurements published by [BLE Scale Sync](https://github.com/KristianP26/ble-scale-sync). Everything runs on your Home Assistant host: no cloud calls, no telemetry, no CDN assets.

## Requirements
- Home Assistant OS or Supervised.
- The Mosquitto broker add-on (or another MQTT broker).
- BLE Scale Sync with its MQTT exporter enabled. The default topic is `scale/body-composition/<user>`.

## Installation
1. Copy this repository to the host, or add it as a local add-on under `/addons`.
2. In **Settings → Add-ons → Add-on store**, refresh and install **Body Trends**.
3. Start the add-on and enable **Show in sidebar**.

## Options
| Option | Default | Meaning |
|---|---|---|
| `base_topic` | `scale/body-composition` | Must match BLE Scale Sync's MQTT `topic`. |
| `smoothing_alpha` | `0.1` | Daily smoothing factor of the trend line (Hacker's Diet). Lower is smoother. |
| `hampel_window` | `7` | Number of readings used to judge whether a reading is an outlier. |
| `hampel_sigmas` | `3.5` | How far from the local median (in robust standard deviations) a reading must be to be flagged. |
| `mqtt_host`, `mqtt_port`, `mqtt_username`, `mqtt_password` | broker from the Supervisor | Only set these to override the broker found automatically. |

## Using the dashboard
- Pick a user, then a range (Week, Month, 3M, Year, All). Use the arrows to move back and forth.
- Open each user's **profile** card and set height, sex, birth year and goal weight. Fat mass, FFMI, body-fat category, BMI and the goal ETA need these.
- Flagged outliers are listed under **Data quality**. They are excluded from trends but never deleted.
- Impedance-based body fat is noisy. Read the trend, not single values.

## What is calculated
- **Trend line:** exponentially weighted moving average, adjusted for gaps between weigh-ins.
- **Rate of change:** Theil–Sen robust slope over 7, 30 and 90 days (per week). "Plateau" means the 95% interval of the slope includes zero.
- **Forecast:** damped Holt linear trend for 60 days with a prediction band, and an ETA to the goal weight.
- **Composition:** fat and lean mass, normalized FFMI, WHO BMI categories, ACE body-fat categories.
- **Patterns:** weekday offsets from trend, weekly and monthly means.

## Entities
For each user the add-on creates a device through MQTT discovery with these sensors: trend weight, weight change (30d, kg/week), trend body fat, and lean mass. It also creates an **Export trends** button.

## Exporting for analysis with Claude
**From the panel:** choose Markdown, JSON or CSV and press **Export**. Markdown contains a summary, trends, weekly table, recent readings and a ready-to-paste prompt.

**From Home Assistant:** pressing the **Export trends** button writes `/share/body_trends/exports/<user>-trends.md`. Fetch it with Samba, SSH or the File editor.

**Anonymize** (on by default) replaces the username with "person", dates with "day N", and removes birth year and impedance values. Exports only happen when you request them.

## Importing history
BLE Scale Sync publishes live weigh-ins only. To backfill, upload a CSV (header row with `timestamp`, `weight` and any of `bodyFatPercent`, `waterPercent`, `muscleMass`, `boneMass`, `visceralFat`, `bmi`, `bmr`, `metabolicAge`) or a JSON list of such objects:

```
curl -F file=@history.csv http://<add-on-host>:8099/api/import/<user>
```
The port is not exposed by default. Either enable it under the add-on's **Network** settings, or use `docker exec` on the host. Duplicates, by user and timestamp, are skipped.

## Data and privacy
- Data lives in the add-on's `/data/body.db` and is included in Home Assistant backups.
- The UI is reachable only through Home Assistant ingress.
- The add-on connects only to your MQTT broker.

## Troubleshooting
- **No users appear:** check that `base_topic` matches BLE Scale Sync and look at the add-on log for "Ignoring unusable payload". Payloads need `timestamp` and a positive `weight`.
- **Entities missing:** discovery needs MQTT discovery enabled in Home Assistant, with the default `homeassistant` prefix.
