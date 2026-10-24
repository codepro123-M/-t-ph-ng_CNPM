const amenity = ['Free WiFi', 'Free Breakfast', 'Room Service', 'Mountain View', 'Pool Access'];
export const demoStays = [
  ['1','The Grand Resort','Double Bed',399,'room1.png','New York','123 Main Road, Downtown, New York'],
  ['2','The Grand Resort','Single Bed',299,'room2.png','New York','123 Main Road, Downtown, New York'],
  ['3','The Grand Resort','Luxury Room',249,'room3.png','London','24 Park Lane, Mayfair, London'],
  ['4','The Grand Resort','Family Suite',199,'room4.png','Singapore','10 Bayfront Avenue, Marina Bay, Singapore'],
  ['5','The Grand Resort','Double Bed',249,'room1.png','Dubai','8 Palm Crescent, Palm Jumeirah, Dubai'],
].map(([n,name,roomType,price,image,city,address],i)=>({
  id:'demo-'+n,name,roomType,category:'resort',address,city,
  description:'Step into a space where thoughtful design meets effortless comfort. Wake up to beautiful views, unwind in a beautifully appointed room, and make yourself at home. From a quiet morning coffee to an evening by the pool, every detail is designed around your stay.',
  check_in_instructions:'Check-in from 2:00 PM. Please bring a photo ID and your booking confirmation. Our front desk is here to welcome you 24 hours a day.',
  images:['/assets/'+image,...['room1.png','room2.png','room3.png','room4.png'].filter(x=>x!==image).map(x=>'/assets/'+x)],
  language:'en',requested_language:'en',audio_url:null,latitude:40.758,longitude:-73.9855,rating:'4.9',reviews:200,
  menu_items:[{id:'room-'+n,name:roomType,kind:'room_type',description:'A spacious retreat with a comfortable bed and a private bathroom.',price,currency:'USD',capacity:i===3?4:2,amenities:amenity.slice(0,i===1?3:5),is_available:true}],
  sample:true,
}));
export const offers = [
 {id:1,image:'/assets/offer1.png',discount:25,title:'Summer Escape Package',description:'Enjoy a complimentary night and daily breakfast.',expiry:'Aug 31'},
 {id:2,image:'/assets/offer2.png',discount:20,title:'Romantic Getaway',description:'Special couples package including a romantic dinner.',expiry:'Sep 20'},
 {id:3,image:'/assets/offer3.png',discount:30,title:'Luxury Retreat',description:'Book in advance and save on your next luxury stay.',expiry:'Sep 25'},
];
export const reviews=[
 {name:'Emma Rodriguez',location:'Barcelona, Spain',image:'/assets/guest1.jpg',text:"I've used many booking platforms before, but none compare to the personalized experience and attention to detail that QuickStay provides. Their curated selection of hotels is unmatched."},
 {name:'Liam Johnson',location:'New York, USA',image:'/assets/guest2.jpg',text:'QuickStay exceeded my expectations. The booking process was seamless, and the hotels were absolutely top-notch. Highly recommended!'},
 {name:'Sophia Lee',location:'Seoul, South Korea',image:'/assets/guest3.jpg',text:'Amazing service! I always find the best luxury accommodations through QuickStay. Their recommendations never disappoint!'},
];
export const sampleBookings=[
 {id:'sample-1',stayId:'demo-1',name:'The Grand Resort',room:'Double Bed',image:'/assets/room1.png',address:'123 Main Road, Downtown, New York',price:598,guests:2,checkIn:'2026-11-06',checkOut:'2026-11-08',paid:true,sample:true},
 {id:'sample-2',stayId:'demo-3',name:'The Grand Resort',room:'Luxury Room',image:'/assets/room3.png',address:'24 Park Lane, Mayfair, London',price:798,guests:2,checkIn:'2026-11-12',checkOut:'2026-11-14',paid:false,sample:true},
 {id:'sample-3',stayId:'demo-2',name:'The Grand Resort',room:'Single Bed',image:'/assets/room2.png',address:'123 Main Road, Downtown, New York',price:398,guests:1,checkIn:'2026-12-04',checkOut:'2026-12-06',paid:true,sample:true},
];
