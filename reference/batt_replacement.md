# A DIY Battery Replacement

(C) 2024-2025 [ekspla](https://github.com/ekspla/xoss_sync)

During a bicycle ride on a chilly winter in Dec. 2023, my XOSS G+ suddenly stopped working. 
That was caused by the degraded battery (about 4 years & 28000 km of use) and the cold 
atmosphere at around 0 deg C. I replaced the battery by myself after the ride. 


My DIY fix needed tools as followings,

a sharp knife, a pair of tweezers, a fine screw driver and a soldering iron.


The fix was not very difficult, but I had to be very careful in opening the backpanel. 
This was because the six phillips screws on the backpanel were sealed by glue to make them 
water resistant. I used the sharp knife and the tweezers to remove the glue on the screws 
very carefully.

Once the glue removed, to unscrew and open the backpanel were quite easy.
![Fig_XOSS_unscrewed](https://github.com/ekspla/xoss_sync/blob/main/reference/Fig_XOSS_unscrewed.jpg "XOSS G+ opened")

The damaged battery was sticked on inside the backpanel by an adhesive tape. Because 
the connection points on the PCB were kindly marked as B+/-, there was little risk to 
connect the new battery wires in the opposite direction.


A replacement battery (503035 with a protection circuit, 3.7 V 500 mAh) could be easily 
obtained on any ec stores (Amazon, ebay, Aliexpress, Taobao, etc.) for less than 5 US$.

After the replacement by soldering, I switched off the power and closed the backpanel 
without the glue.


The capacity of the degraded battery at full charge was measured by a constant current 
sink of 0.5C to be 260 mAh at room temperature of 20 deg C.  It was degraded in 
capacity to about a half.

![Fig_old_LiPo_capacity.png](https://github.com/ekspla/xoss_sync/blob/main/reference/Fig_old_LiPo_capacity.png "Degraded Capacity")
