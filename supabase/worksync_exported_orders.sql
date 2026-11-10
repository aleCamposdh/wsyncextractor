-- PO# de Mungo Homes que ya se incluyeron en una descarga CSV o Excel.
create table if not exists public.worksync_exported_orders (
  order_key text primary key,
  source text not null check (source = 'Mungo Homes'),
  exported_at timestamptz not null default now()
);

grant usage on schema public to service_role;
grant all privileges on table public.worksync_exported_orders to service_role;
