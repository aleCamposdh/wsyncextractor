create extension if not exists pgcrypto;

create table if not exists public.worksync_reminders (
  id uuid primary key default gen_random_uuid(),
  description text not null check (length(trim(description)) > 0),
  reminder_date date not null,
  assignees text[] not null default '{}',
  acknowledged boolean not null default false,
  acknowledged_at timestamptz,
  created_at timestamptz not null default now()
);

alter table public.worksync_reminders
add column if not exists assignees text[] not null default '{}';

create index if not exists worksync_reminders_date_idx
on public.worksync_reminders (reminder_date, acknowledged);

grant usage on schema public to service_role;
grant all privileges on table public.worksync_reminders to service_role;
