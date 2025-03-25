-- license:MIT
-- copyright-holders:Custom
-- MAME Controls Menu Plugin for MAME 0.196
local exports = {}
exports.name = "controls"
exports.version = "0.1.196"
exports.description = "MAME Controls Display Menu"
exports.license = "MIT"
exports.author = { name = "Custom" }

function exports.startplugin()
    local controls_shown = false
    
    local function show_controls()
        if controls_shown then return end
        
        local game_name = emu.romname()
        print("Game: " .. (game_name or "nil"))
        
        if game_name and game_name ~= "" then
            local command = string.format('pythonw "MAME Controls.pyw" --preview-only --game %s --screen 1', game_name)
            print("Running: " .. command)
            os.execute(command)
            controls_shown = true
        end
    end
    
    -- Wait a few seconds before showing controls
    local start_time = os.time()
    
    emu.register_periodic(function()
        -- Wait 3 seconds before showing controls
        if not controls_shown and os.time() - start_time > 1 then
            show_controls()
        end
    end)
    
    print("Controls plugin loaded (periodic version)")
end

return exports