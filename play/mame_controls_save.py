import os
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog
from PyQt5.QtGui import QPainter, QImage, QFont, QColor, QFontMetrics
from PyQt5.QtCore import Qt, QSize, QRect, QPoint

class SaveUtility:
    """Utility class for saving preview images and configurations"""
    
    @staticmethod
    def save_preview_image(preview_canvas, rom_name, mame_dir):
        """Save the current preview state as an image"""
        # Create preview directory if it doesn't exist
        preview_dir = os.path.join(mame_dir, "preview")
        if not os.path.exists(preview_dir):
            os.makedirs(preview_dir)
            
        # Define the output path
        output_path = os.path.join(preview_dir, f"{rom_name}.png")
        
        # Check if file already exists
        if os.path.exists(output_path):
            # Ask for confirmation
            if not QMessageBox.question(
                None, 
                "Confirm Overwrite", 
                f"Image already exists for {rom_name}. Overwrite?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes:
                return False
        
        try:
            # Create a new image with the same size as the canvas
            image = QImage(
                preview_canvas.size(),
                QImage.Format_ARGB32
            )
            image.fill(Qt.black)
            
            # Create painter for the image
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            
            # Draw background if available
            if preview_canvas.background_pixmap:
                # Scale pixmap to fit widget while maintaining aspect ratio
                scaled_pixmap = preview_canvas.background_pixmap.scaled(
                    preview_canvas.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                
                # Calculate position to center the pixmap
                x = (preview_canvas.width() - scaled_pixmap.width()) // 2
                y = (preview_canvas.height() - scaled_pixmap.height()) // 2
                
                # Draw the pixmap
                painter.drawPixmap(x, y, scaled_pixmap)
            
            # Draw text items (controls)
            for control_name, label in preview_canvas.text_items.items():
                if not label.isVisible():
                    continue
                    
                # Get text and position
                text = label.text()
                pos = label.pos()
                
                # Remove HTML formatting if present
                if "<span" in text:
                    # Simple HTML stripping - in a real implementation,
                    # you'd want more robust HTML parsing
                    text = text.replace("<span style=\"text-shadow: 2px 2px #000000\">", "")
                    text = text.replace("</span>", "")
                
                # Draw text with shadow effect
                font = QFont("Arial", 18, QFont.Bold)
                painter.setFont(font)
                
                # Shadow
                painter.setPen(QColor(0, 0, 0))
                painter.drawText(pos.x() + 2, pos.y() + 2 + QFontMetrics(font).height(), text)
                
                # Main text
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(pos.x(), pos.y() + QFontMetrics(font).height(), text)
            
            # End painting
            painter.end()
            
            # Save the image
            image.save(output_path, "PNG")
            
            QMessageBox.information(
                None,
                "Success",
                f"Image saved to:\n{output_path}"
            )
            
            return True
            
        except Exception as e:
            QMessageBox.critical(
                None,
                "Error",
                f"Failed to save image: {str(e)}"
            )
            return False
    
    @staticmethod
    def export_control_data(game_data, mame_dir):
        """Export control data to a text file"""
        # Create export directory if it doesn't exist
        export_dir = os.path.join(mame_dir, "exports")
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)
            
        # Define the output path
        output_path = os.path.join(export_dir, f"{game_data['romname']}_controls.txt")
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # Write header
                f.write(f"Control Data for {game_data['gamename']} ({game_data['romname']})\n")
                f.write("="*80 + "\n\n")
                
                # Write game info
                f.write(f"Players: {game_data['numPlayers']}\n")
                f.write(f"Alternating: {game_data['alternating']}\n")
                if 'miscDetails' in game_data:
                    f.write(f"Details: {game_data['miscDetails']}\n")
                f.write("\n")
                
                # Write player controls
                for player in game_data.get('players', []):
                    f.write(f"Player {player['number']} Controls:\n")
                    f.write("-"*20 + "\n")
                    
                    for label in player.get('labels', []):
                        f.write(f"{label['name']}: {label['value']}\n")
                    
                    f.write("\n")
            
            return True
            
        except Exception as e:
            print(f"Error exporting control data: {e}")
            return False