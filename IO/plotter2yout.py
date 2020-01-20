def plotter2yout(dic):
    import matplotlib as plt
    fig, ax1 = plt.subplots()

    color = 'tab:red'
    ax1.set_xlabel('Volume (ml)')
    ax1.set_ylabel('Absorbance (mAU)')
    ax1.plot(dic['volume (ml)'],dic['Absorbance (mAU)'],color=color)
    ax1.set_ylim(ymin=0)
    ax1.set_xlim(xmin=0)
    ax1.tick_params(axis="y",labelcolor=color)

    ax2 = ax1.twinx()

    color = 'tab:blue'
    ax2.set_ylabel("Conc B (%)(ml)") 
    ax2.plot(dic['volume (ml)'],dic['Buffer B Concentration (%)'],color=color)
    ax2.set_ylim(ymin=0)
    ax2.tick_params(axis='y', labelcolor=color)
    fig.tight_layout()

    plt.savefig('results.png', bbox_inches='tight', dpi=150)
    print("saved to results.png")
