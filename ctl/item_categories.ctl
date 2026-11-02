OPTIONS (SKIP=1, ERRORS=0, BINDSIZE=10485760, READSIZE=10485760, ROWS=50000)
LOAD DATA
INFILE 'data/prepared/item_categories.csv'
BADFILE 'logs/item_categories.bad'
DISCARDFILE 'logs/item_categories.dsc'
INTO TABLE stg_item_categories
TRUNCATE
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
TRAILING NULLCOLS
(
    itemid        INTEGER EXTERNAL,
    categoryid    INTEGER EXTERNAL
)
