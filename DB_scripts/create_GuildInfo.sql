CREATE TABLE "GuildInfo" (
	"GuildId" INTEGER NOT NULL UNIQUE,
	"GuildName" TEXT NOT NULL,
	"BotChannel" INTEGER,
	"LastUpdated" TEXT NOT NULL,
	PRIMARY KEY("GuildId")
);