CREATE TABLE IF NOT EXISTS analytics_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at TEXT NOT NULL,
  day TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('page_view', 'product_click')),
  product_key TEXT NOT NULL DEFAULT '',
  product_title TEXT NOT NULL DEFAULT '',
  store TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  page_path TEXT NOT NULL DEFAULT '/',
  referrer_host TEXT NOT NULL DEFAULT '',
  device_type TEXT NOT NULL DEFAULT '',
  country TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_analytics_day_type
  ON analytics_events(day, event_type);

CREATE INDEX IF NOT EXISTS idx_analytics_product
  ON analytics_events(event_type, product_key, day);

CREATE INDEX IF NOT EXISTS idx_analytics_category
  ON analytics_events(category, day);

