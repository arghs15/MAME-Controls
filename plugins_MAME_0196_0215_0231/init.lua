-- Simple controls plugin for MAME 0.231
local exports = {}
exports.name = "controls"
exports.version = "0.1"
exports.description = "Controls Display"
exports.license = "MIT"
exports.author = { name = "Custom" }

function exports.startplugin()
    local function show_controls()
        local game_name = emu.romname()
        if game_name and game_name ~= "" then
            -- Run the controls viewer application
            local command = string.format('pythonw "MAME Controls.pyw" --preview-only --game %s --screen 1', game_name)
            os.execute(command)
        end
    end

    -- Register pause handler
    emu.register_pause(function()
        show_controls()
    end)
    
    -- Add simple menu option
    emu.register_menu(
        function(index, event)
            if event == "select" then
                emu.pause()
                show_controls()
                emu.unpause()
                return true
            end
            return false
        end,
        function()
            return {{"Show Controls", "", 0}}
        end,
        "Controls"
    )
    
    print("Controls plugin loaded")
end

return exports