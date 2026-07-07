CREATE EXTENSION IF NOT EXISTS matrixts;
CREATE EXTENSION IF NOT EXISTS postgres_fdw;
SELECT apm_enable_partition_maintenance();

CREATE TABLE dim_date (
    date_key DATE, year SMALLINT, quarter SMALLINT, month SMALLINT,
    week SMALLINT, day_of_month SMALLINT, day_of_week SMALLINT,
    is_weekend BOOLEAN, season VARCHAR(4)
) USING HEAP DISTRIBUTED BY (date_key);

INSERT INTO dim_date (date_key, year, quarter, month, week, day_of_month, day_of_week, is_weekend, season)
SELECT d::DATE,
    EXTRACT(YEAR FROM d)::SMALLINT, EXTRACT(QUARTER FROM d)::SMALLINT,
    EXTRACT(MONTH FROM d)::SMALLINT, EXTRACT(WEEK FROM d)::SMALLINT,
    EXTRACT(DAY FROM d)::SMALLINT, EXTRACT(DOW FROM d)::SMALLINT + 1,
    EXTRACT(DOW FROM d) IN (0,6),
    CASE WHEN EXTRACT(MONTH FROM d) IN (3,4,5) THEN 'spring'
         WHEN EXTRACT(MONTH FROM d) IN (6,7,8) THEN 'summer'
         WHEN EXTRACT(MONTH FROM d) IN (9,10,11) THEN 'autumn'
         ELSE 'winter' END
FROM generate_series('2023-01-01'::DATE, '2025-12-31'::DATE, '1 day') d;

CREATE TABLE etl_log (
    log_id BIGSERIAL, step VARCHAR(50), status VARCHAR(20),
    rows_processed INT, duration_ms INT, message TEXT,
    log_time TIMESTAMP DEFAULT current_timestamp
) USING MARS3 DISTRIBUTED BY (log_id) ORDER BY (log_time);
