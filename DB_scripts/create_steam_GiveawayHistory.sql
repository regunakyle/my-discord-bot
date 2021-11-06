CREATE TABLE "steam_GiveawayHistory" (
	"Title"	TEXT NOT NULL,
	"Link"	TEXT NOT NULL,
	"PublishTime"	TEXT NOT NULL,
	"ExpiryDate"	TEXT,
	PRIMARY KEY("Title","PublishTime")
)