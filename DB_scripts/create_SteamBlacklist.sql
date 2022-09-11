CREATE TABLE "SteamBlacklist" (
	"Keyword" TEXT NOT NULL,
	"GuildId" TEXT NOT NULL,
	"Timestamp" TEXT NOT NULL,
	PRIMARY KEY("Keyword")
);