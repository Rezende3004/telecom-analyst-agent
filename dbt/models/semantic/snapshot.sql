select snapshot_date, receita_mes from {{ source('raw', 'snapshot') }}
