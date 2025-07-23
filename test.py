from PyQt5.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsRectItem
import sys

app = QApplication(sys.argv)
scene = QGraphicsScene()
view = QGraphicsView(scene)

# Add a draggable node
node = QGraphicsRectItem(0, 0, 100, 50)
node.setFlag(QGraphicsRectItem.ItemIsMovable)
scene.addItem(node)

view.show()
sys.exit(app.exec_())
