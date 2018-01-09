BEGIN TRANSACTION;
CREATE TABLE `comments` (
	`slack_user`	TEXT,
	`date`	TEXT,
	`author`	TEXT,
	`body`	INTEGER,
	`score`	INTEGER
);
CREATE TABLE "accounts" (
	`name`	TEXT,
	`slack_user`	TEXT,
	`special_class`	TEXT,
	`added`	TEXT,
	`can_submit`	TEXT,
	`num_submissions`	INTEGER,
	`last_submitted`	TEXT,
	`can_comment`	INTEGER,
	`last_commented`	INTEGER,
	`num_comments`	INTEGER
);
COMMIT;
