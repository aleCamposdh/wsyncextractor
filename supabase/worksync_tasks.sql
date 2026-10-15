create extension if not exists pgcrypto;

create table if not exists public.worksync_tasks (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text not null default '',
  assignee text not null check (assignee in ('Danna', 'Karen', 'Nia', 'Tatiana')),
  priority text not null check (priority in ('Alta', 'Media', 'Baja')),
  due_date date not null,
  completed boolean not null default false,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Reconcile an earlier generic worksync_tasks table, if it already existed.
alter table public.worksync_tasks
add column if not exists assigned_to text not null default '';

alter table public.worksync_tasks
add column if not exists assignee text;

alter table public.worksync_tasks
add column if not exists completed boolean not null default false;

update public.worksync_tasks
set assignee = coalesce(nullif(assignee, ''), nullif(assigned_to, ''), 'Danna')
where assignee is null or assignee = '';

alter table public.worksync_tasks
alter column assignee set not null;

alter table public.worksync_tasks
drop constraint if exists worksync_tasks_assignee_check;

alter table public.worksync_tasks
add constraint worksync_tasks_assignee_check
check (assignee in ('Danna', 'Karen', 'Nia', 'Tatiana'));

alter table public.worksync_tasks
drop constraint if exists worksync_tasks_priority_check;

update public.worksync_tasks
set priority = case lower(priority)
  when 'high' then 'Alta'
  when 'urgent' then 'Alta'
  when 'normal' then 'Media'
  when 'medium' then 'Media'
  when 'low' then 'Baja'
  else priority
end;

alter table public.worksync_tasks
add constraint worksync_tasks_priority_check
check (priority in ('Alta', 'Media', 'Baja'));

create index if not exists worksync_tasks_priority_due_date_idx
on public.worksync_tasks (priority, due_date);

grant usage on schema public to service_role;
grant all privileges on table public.worksync_tasks to service_role;
