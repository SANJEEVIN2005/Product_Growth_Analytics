OPTIONS (SKIP=1, ERRORS=0)
LOAD DATA
INFILE 'data/raw/category_tree.csv'
BADFILE 'logs/category_tree.bad'
DISCARDFILE 'logs/category_tree.dsc'
INTO TABLE stg_category_tree
TRUNCATE
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
TRAILING NULLCOLS
(
    categoryid    INTEGER EXTERNAL,
    parentid      INTEGER EXTERNAL NULLIF parentid=BLANKS
)
