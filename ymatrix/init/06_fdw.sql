DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'mysql_fdw') THEN
        RAISE NOTICE 'mysql_fdw is available; optional cross-database setup can be enabled separately';
    ELSE
        RAISE NOTICE 'mysql_fdw is unavailable in this image; skipping optional FDW showcase';
    END IF;
END
$$;
