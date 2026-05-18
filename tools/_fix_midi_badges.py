"""Fix badge textContent lines in midi-learn.js"""
path = "frontend/js/midi-learn.js"
content = open(path, encoding="utf-8").read()

old1 = "                if (badge) badge.textContent = `CH${channel} CC${ccNumber}`;"
new1 = "                if (badge) badge.textContent = _formatBadge(channel, ccNumber, gridPlayer, gridCol, gridRow);"

old2 = "                    if (badge) badge.textContent = `CH${m.channel ?? 1} CC${m.number}`;"
new2 = "                    if (badge) badge.textContent = _formatBadge(m.channel ?? 1, m.number, m.grid_player || 'video', m.grid_col ?? -1, m.grid_row ?? -1);"

print("old1 found:", old1 in content)
print("old2 found:", old2 in content)

content = content.replace(old1, new1)
content = content.replace(old2, new2)

open(path, "w", encoding="utf-8").write(content)
print("Done. _formatBadge count:", content.count("_formatBadge"))
