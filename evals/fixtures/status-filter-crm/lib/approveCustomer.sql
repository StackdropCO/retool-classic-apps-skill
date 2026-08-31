UPDATE public.customers
SET status       = 'approved',
    bonus_points = bonus_points + 50,
    updated_at   = now()
WHERE id = {{ customersTable.selectedRow.id }}
RETURNING id, name, status, bonus_points
