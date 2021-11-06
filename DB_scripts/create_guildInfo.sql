CREATE TABLE "guildInfo" (
	"GuildId"	INTEGER NOT NULL UNIQUE,
	"GuildName"	TEXT NOT NULL,
	"BotChannel"	TEXT,
	"LastUpdated"	TEXT NOT NULL,
	PRIMARY KEY("GuildId")
)