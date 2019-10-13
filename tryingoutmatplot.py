import matplotlib.pyplot as plt
import numpy as np

N = np.random.randint(1,1000)
x = np.random.rand(N)
y = np.random.rand(N)
colors = np.random.rand(N)
area = 100*np.pi*np.random.rand(N)
alpha = np.random.rand(N)

plt.scatter(x, y, s=area, c=colors, alpha)
plt.title('Coloured dots')
plt.xlabel('x')
plt.ylabel('y')
plt.savefig("out2.png")


