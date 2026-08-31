SELECT
  id,
  name,
  email,
  status,
  notes,
  created_at
FROM public.customers
WHERE ({{ statusFilter.value }} = '' OR status = {{ statusFilter.value }})
ORDER BY name ASC
