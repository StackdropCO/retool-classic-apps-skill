-- 2026-05-10: the catalogue table this workspace's app manages.
-- Run ONCE against the products RDS. Idempotent; safe to re-run.
CREATE TABLE IF NOT EXISTS public.products (
  id         bigserial PRIMARY KEY,
  name       text NOT NULL,
  category   text NOT NULL,
  price      numeric(10,2) NOT NULL CHECK (price >= 0),
  stock      integer NOT NULL DEFAULT 0 CHECK (stock >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
